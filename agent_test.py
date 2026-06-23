#!/usr/bin/env python3
"""
Frontier-agent difficulty calibration for Terminal-Bench tasks.

Runs GPT-5.2 and Claude Opus 4.6 via Snorkel STB (stb harbor run), then
reports pass rates and difficulty bands from job artifacts under jobs/.

Prerequisites:
  export OPENAI_API_KEY=<portkey-api-key>
  export OPENAI_BASE_URL=https://api.portkey.ai/v1
  stb CLI installed (snorkelai-stb)

Examples:
  ./agent_test.py run tasks/my-task
  ./agent_test.py run tasks/my-task --runs 5 --models gpt-5.2
  ./agent_test.py report jobs/2026-05-20__05-13-51
  ./agent_test.py report --latest --task my-task
  ./agent_test.py trial jobs/2026-05-20__05-13-51/sustained-churn-footprint__xnKe3YE
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Harbor / STB model flags (see platform agent-testing guide).
MODELS: dict[str, dict[str, str]] = {
    "gpt-5.2": {
        "label": "GPT-5.2",
        "harbor_flag": "@openai/gpt-5.2",
        "match": r"gpt-5\.2",
    },
    "claude-opus-4.6": {
        "label": "Claude Opus 4.6",
        "harbor_flag": "@anthropic/claude-opus-4-6",
        "match": r"claude-opus-4-6",
    },
}

DEFAULT_RUNS = 5
ACCEPTANCE_NOTE = (
    "Edition 2 repo accepts hard tasks only; platform also rejects worst-model > 80%."
)


@dataclass(frozen=True)
class ModelRunStats:
    model_id: str
    label: str
    passes: int
    trials: int
    errors: int
    pass_rate: float

    @property
    def failures(self) -> int:
        return self.trials - self.passes - self.errors


@dataclass(frozen=True)
class DifficultyVerdict:
    label: str
    detail: str
    accepted: bool


@dataclass(frozen=True)
class TrialFailureAnalysis:
    """Heuristic good-fail vs bad-fail classification from local job artifacts."""

    trial_dir: str
    trial_name: str
    model_id: str | None
    outcome: str  # pass | fail_good | fail_bad | review
    confidence: str  # high | medium | low
    category: str
    reason: str
    review_paths: tuple[str, ...]


# Exception types / messages that indicate infrastructure or harness problems.
_BAD_INFRA_EXCEPTION_TYPES = frozenset(
    {
        "APIError",
        "AuthenticationError",
        "RateLimitError",
        "TimeoutError",
        "AgentTimeoutError",
        "VerifierTimeoutError",
        "CancelledError",
        "DockerError",
        "BuildError",
    }
)
_BAD_INFRA_MESSAGE_RE = re.compile(
    r"(?i)(portkey|api key|usage limit|rate limit|authentication|"
    r"agenttimeout|verifiertimeout|cancelled|docker|build failed|"
    r"connection refused|connection reset|out of memory|oom)"
)
_BAD_HARNESS_MESSAGE_RE = re.compile(
    r"(?i)(tmux|send non-blocking keys|harbor/trial|harbor/agents|"
    r"litellm\.|session_id)"
)
_HARNESS_TEST_RE = re.compile(
    r"(?i)(ERROR collecting|ModuleNotFoundError|ImportError|"
    r"SyntaxError: |collected 0 items|No module named |"
    r"fixture .* not found|INTERNALERROR)"
)
_DOMAIN_ASSERT_RE = re.compile(r"AssertionError")
_OUTPUT_MISSING_RE = re.compile(
    r"(?i)(FileNotFoundError|No such file or directory|"
    r"json\.decoder\.JSONDecodeError|Expecting value)"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _read_task_difficulty(task_dir: Path) -> str | None:
    toml_path = task_dir / "task.toml"
    if not toml_path.is_file():
        return None
    text = toml_path.read_text(encoding="utf-8")
    match = re.search(r'^\s*difficulty\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _trial_dirs(job_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in job_dir.iterdir()
        if path.is_dir() and (path / "result.json").exists()
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path, *, limit: int = 120_000) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _trial_payload(trial_dir: Path) -> dict[str, Any] | None:
    return _read_json(trial_dir / "result.json")


def _agent_episodes(payload: dict[str, Any]) -> int | None:
    meta = ((payload.get("agent_result") or {}).get("metadata")) or {}
    episodes = meta.get("n_episodes")
    return int(episodes) if isinstance(episodes, int) else None


def _trial_model_id(payload: dict[str, Any]) -> str | None:
    agent_cfg = ((payload.get("config") or {}).get("agent")) or {}
    model_name = str(agent_cfg.get("model_name") or "")
    info_name = str(((payload.get("agent_info") or {}).get("model_info") or {}).get("name") or "")
    return _match_model_id(model_name) or _match_model_id(info_name)


def _ctrf_summary(trial_dir: Path) -> dict[str, Any]:
    ctrf = _read_json(trial_dir / "verifier" / "ctrf.json")
    if not ctrf:
        return {}
    summary = ((ctrf.get("results") or {}).get("summary")) or {}
    tests = (((ctrf.get("results") or {}).get("tests")) or [])
    statuses = [str(t.get("status", "")).lower() for t in tests]
    traces = "\n".join(str(t.get("trace") or "") for t in tests)
    messages = "\n".join(str(t.get("message") or "") for t in tests)
    return {
        "tests": int(summary.get("tests") or 0),
        "passed": int(summary.get("passed") or 0),
        "failed": int(summary.get("failed") or 0),
        "statuses": statuses,
        "traces": traces,
        "messages": messages,
    }


def _trial_review_paths(trial_dir: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for rel in (
        "result.json",
        "verifier/ctrf.json",
        "verifier/test-stdout.txt",
        "agent/terminus_2.pane",
    ):
        if (trial_dir / rel).exists():
            paths.append(rel)
    agent_dir = trial_dir / "agent"
    if agent_dir.is_dir():
        episodes = sorted(agent_dir.glob("episode-*"))
        if episodes:
            paths.append(str(episodes[-1].relative_to(trial_dir)))
    return tuple(paths)


def classify_trial(trial_dir: Path) -> TrialFailureAnalysis:
    """Classify one trial directory using result.json + verifier artifacts."""
    trial_dir = trial_dir.expanduser().resolve()
    trial_name = trial_dir.name
    review_paths = _trial_review_paths(trial_dir)

    payload = _trial_payload(trial_dir)
    if payload is None:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=None,
            outcome="fail_bad",
            confidence="high",
            category="missing_result",
            reason="Unreadable or missing result.json.",
            review_paths=review_paths,
        )

    model_id = _trial_model_id(payload)
    episodes = _agent_episodes(payload)

    verifier = payload.get("verifier_result") or {}
    rewards = (verifier.get("rewards") or {}) if isinstance(verifier, dict) else {}
    reward = rewards.get("reward")
    if reward == 1.0:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="pass",
            confidence="high",
            category="pass",
            reason="Verifier reward == 1.0 (full pass).",
            review_paths=review_paths,
        )

    exc = payload.get("exception_info") or {}
    if exc:
        exc_type = str(exc.get("exception_type") or "Exception")
        exc_msg = str(exc.get("exception_message") or "")
        exc_tb = str(exc.get("exception_traceback") or "")
        combined = f"{exc_type} {exc_msg} {exc_tb}"

        if exc_type in _BAD_INFRA_EXCEPTION_TYPES or _BAD_INFRA_MESSAGE_RE.search(combined):
            return TrialFailureAnalysis(
                trial_dir=str(trial_dir),
                trial_name=trial_name,
                model_id=model_id,
                outcome="fail_bad",
                confidence="high",
                category="infra_api" if "API" in exc_type or "portkey" in combined.lower() else "infra",
                reason=f"Agent/infra exception before a clean verifier result: {exc_type}.",
                review_paths=review_paths,
            )

        if _BAD_HARNESS_MESSAGE_RE.search(combined):
            return TrialFailureAnalysis(
                trial_dir=str(trial_dir),
                trial_name=trial_name,
                model_id=model_id,
                outcome="fail_bad",
                confidence="high",
                category="harness_crash",
                reason=f"Harbor/terminal harness crash: {exc_type}.",
                review_paths=review_paths,
            )

        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_bad",
            confidence="medium",
            category="agent_crash",
            reason=f"Unhandled agent exception: {exc_type}.",
            review_paths=review_paths,
        )

    if payload.get("verifier_result") is None:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_bad",
            confidence="high",
            category="no_verifier",
            reason="Verifier never produced a result (agent or env failed early).",
            review_paths=review_paths,
        )

    test_stdout = _read_text(trial_dir / "verifier" / "test-stdout.txt")
    if _HARNESS_TEST_RE.search(test_stdout):
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_bad",
            confidence="high",
            category="harness_tests",
            reason="Pytest collection/import/harness error in verifier/test-stdout.txt.",
            review_paths=review_paths,
        )

    ctrf = _ctrf_summary(trial_dir)
    if ctrf.get("tests") == 0 and test_stdout and "collected" in test_stdout.lower():
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_bad",
            confidence="medium",
            category="harness_empty",
            reason="Verifier ran but collected zero tests.",
            review_paths=review_paths,
        )

    if episodes == 0:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_bad",
            confidence="high",
            category="agent_no_work",
            reason="Agent completed zero episodes (did not meaningfully attempt the task).",
            review_paths=review_paths,
        )

    passed = int(ctrf.get("passed") or 0)
    failed = int(ctrf.get("failed") or 0)
    traces = str(ctrf.get("traces") or "")
    combined_test = f"{test_stdout}\n{traces}"

    if passed > 0 and failed > 0:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_good",
            confidence="high",
            category="partial_pass",
            reason=f"Partial verifier pass ({passed}/{passed + failed} tests) — likely legitimate difficulty.",
            review_paths=review_paths,
        )

    if _DOMAIN_ASSERT_RE.search(combined_test) or "assert " in combined_test.lower():
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_good",
            confidence="high" if (episodes or 0) >= 2 else "medium",
            category="domain_assertion",
            reason="Verifier assertion failures on task outputs/metrics (agent tried, requirements not met).",
            review_paths=review_paths,
        )

    if _OUTPUT_MISSING_RE.search(combined_test):
        confidence = "medium" if (episodes or 0) >= 1 else "low"
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_good",
            confidence=confidence,
            category="missing_outputs",
            reason="Expected outputs/artifacts missing or invalid — often agent reasoning gap; spot-check instructions.",
            review_paths=review_paths,
        )

    if (episodes or 0) >= 1 and reward == 0.0:
        return TrialFailureAnalysis(
            trial_dir=str(trial_dir),
            trial_name=trial_name,
            model_id=model_id,
            outcome="fail_good",
            confidence="medium",
            category="verifier_fail",
            reason="Verifier failed after agent ran; no harness signals — treat as likely good fail.",
            review_paths=review_paths,
        )

    return TrialFailureAnalysis(
        trial_dir=str(trial_dir),
        trial_name=trial_name,
        model_id=model_id,
        outcome="review",
        confidence="low",
        category="ambiguous",
        reason="Could not classify confidently from artifacts alone — manual review recommended.",
        review_paths=review_paths,
    )


def analyze_job_failures(job_dir: Path) -> list[TrialFailureAnalysis]:
    return [classify_trial(trial) for trial in _trial_dirs(job_dir)]


def summarize_failures(analyses: list[TrialFailureAnalysis]) -> dict[str, Any]:
    counts = {"pass": 0, "fail_good": 0, "fail_bad": 0, "review": 0}
    for item in analyses:
        counts[item.outcome] = counts.get(item.outcome, 0) + 1

    failures = counts["fail_good"] + counts["fail_bad"] + counts["review"]
    bad_share = (counts["fail_bad"] / failures) if failures else 0.0

    if failures == 0:
        trust = "n/a"
        trust_detail = "No failed trials."
    elif bad_share == 0.0 and counts["review"] == 0:
        trust = "high"
        trust_detail = "All failures look like legitimate task difficulty (fail-good)."
    elif bad_share <= 0.2 and counts["review"] <= 1:
        trust = "medium"
        trust_detail = "Most failures look legitimate; spot-check flagged bad/review trials."
    else:
        trust = "low"
        trust_detail = (
            f"{counts['fail_bad']} bad + {counts['review']} review failures — "
            "fix task/env issues before trusting pass-rate difficulty."
        )

    return {
        "counts": counts,
        "trials": len(analyses),
        "difficulty_trust": trust,
        "difficulty_trust_detail": trust_detail,
        "bad_failure_share": bad_share,
    }


def _trial_passed(trial_dir: Path) -> tuple[bool, bool]:
    """Return (passed, is_infra_error)."""
    payload = _trial_payload(trial_dir)
    if payload is None:
        return False, True

    if payload.get("exception_info"):
        return False, True

    verifier = payload.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    reward = rewards.get("reward")
    return reward == 1.0, False


def _match_model_id(eval_key: str) -> str | None:
    for model_id, spec in MODELS.items():
        if re.search(spec["match"], eval_key, re.IGNORECASE):
            return model_id
    return None


def _stats_from_job_result(job_dir: Path) -> dict[str, ModelRunStats]:
    """Parse jobs/<job>/result.json reward_stats when present."""
    result_path = job_dir / "result.json"
    if not result_path.is_file():
        return {}

    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    stats: dict[str, ModelRunStats] = {}
    evals = ((payload.get("stats") or {}).get("evals")) or {}

    for eval_key, eval_payload in evals.items():
        model_id = _match_model_id(eval_key)
        if model_id is None:
            continue

        reward_stats = eval_payload.get("reward_stats") or {}
        reward_map = reward_stats.get("reward") or {}
        passes = len(reward_map.get("1.0") or [])
        fails = len(reward_map.get("0.0") or [])
        trials = int(eval_payload.get("n_trials") or (passes + fails))
        errors = int(eval_payload.get("n_errors") or 0)

        stats[model_id] = ModelRunStats(
            model_id=model_id,
            label=MODELS[model_id]["label"],
            passes=passes,
            trials=trials,
            errors=errors,
            pass_rate=(passes / trials) if trials else 0.0,
        )

    return stats


def _stats_from_trials(job_dir: Path) -> dict[str, ModelRunStats]:
    """Fallback: walk per-trial result.json and group by model_name."""
    buckets: dict[str, dict[str, int]] = {
        model_id: {"passes": 0, "trials": 0, "errors": 0} for model_id in MODELS
    }

    for trial in _trial_dirs(job_dir):
        try:
            payload = json.loads((trial / "result.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        agent_cfg = ((payload.get("config") or {}).get("agent")) or {}
        model_name = str(agent_cfg.get("model_name") or "")
        model_id = _match_model_id(model_name)
        if model_id is None:
            continue

        passed, infra = _trial_passed(trial)
        buckets[model_id]["trials"] += 1
        if infra:
            buckets[model_id]["errors"] += 1
        elif passed:
            buckets[model_id]["passes"] += 1

    stats: dict[str, ModelRunStats] = {}
    for model_id, counts in buckets.items():
        trials = counts["trials"]
        passes = counts["passes"]
        stats[model_id] = ModelRunStats(
            model_id=model_id,
            label=MODELS[model_id]["label"],
            passes=passes,
            trials=trials,
            errors=counts["errors"],
            pass_rate=(passes / trials) if trials else 0.0,
        )
    return {k: v for k, v in stats.items() if v.trials > 0}


def analyze_job_dir(job_dir: Path) -> dict[str, ModelRunStats]:
    job_dir = job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        raise FileNotFoundError(f"job directory not found: {job_dir}")

    stats = _stats_from_job_result(job_dir)
    if stats:
        return stats
    return _stats_from_trials(job_dir)


def classify_difficulty(model_stats: dict[str, ModelRunStats]) -> DifficultyVerdict:
    rates = [s.pass_rate for s in model_stats.values() if s.trials > 0]
    if not rates:
        return DifficultyVerdict(
            label="unknown",
            detail="No frontier-model trials found in job artifacts.",
            accepted=False,
        )

    best = max(rates)
    worst = min(rates)

    if worst > 0.80:
        return DifficultyVerdict(
            label="too_easy",
            detail=(
                f"Worst-model accuracy {worst:.0%} > 80% — task will not be accepted."
            ),
            accepted=False,
        )

    if best <= 0.20 or worst <= 0.20:
        return DifficultyVerdict(
            label="hard",
            detail=(
                f"Best-model {best:.0%}, worst-model {worst:.0%} — "
                "meets hard band (≤20% on best or worst)."
            ),
            accepted=True,
        )

    if 0.20 < worst <= 0.60:
        return DifficultyVerdict(
            label="medium",
            detail=(
                f"Worst-model accuracy {worst:.0%} is in (20%, 60%] — medium band. "
                f"{ACCEPTANCE_NOTE}"
            ),
            accepted=False,
        )

    if 0.60 < worst <= 0.80:
        return DifficultyVerdict(
            label="easy",
            detail=(
                f"Worst-model accuracy {worst:.0%} is in (60%, 80%] — easy band. "
                f"{ACCEPTANCE_NOTE}"
            ),
            accepted=False,
        )

    return DifficultyVerdict(
        label="unknown",
        detail=f"Could not classify (best={best:.0%}, worst={worst:.0%}).",
        accepted=False,
    )


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.0f}%"


def _format_model_line(stats: ModelRunStats) -> str:
    return (
        f"  {stats.label}: {stats.passes}/{stats.trials} = {_pct(stats.pass_rate)}"
        f" ({stats.failures} verifier fails, {stats.errors} infra errors)"
    )


def _analysis_to_dict(item: TrialFailureAnalysis) -> dict[str, Any]:
    return {
        "trial_dir": item.trial_dir,
        "trial_name": item.trial_name,
        "model_id": item.model_id,
        "outcome": item.outcome,
        "confidence": item.confidence,
        "category": item.category,
        "reason": item.reason,
        "review_paths": list(item.review_paths),
    }


def build_report(
    *,
    task_dir: Path | None,
    job_dirs: list[Path],
    declared_difficulty: str | None = None,
    include_failures: bool = True,
) -> dict[str, Any]:
    job_reports: list[dict[str, Any]] = []
    combined: dict[str, ModelRunStats] = {}
    all_failure_analyses: list[TrialFailureAnalysis] = []

    for job_dir in job_dirs:
        per_job = analyze_job_dir(job_dir)
        job_entry: dict[str, Any] = {
            "job_dir": str(job_dir),
            "models": {
                mid: {
                    "passes": s.passes,
                    "trials": s.trials,
                    "errors": s.errors,
                    "pass_rate": s.pass_rate,
                }
                for mid, s in per_job.items()
            },
        }
        if include_failures:
            job_failures = analyze_job_failures(job_dir)
            all_failure_analyses.extend(job_failures)
            job_entry["failures"] = summarize_failures(job_failures)
            job_entry["trials"] = [_analysis_to_dict(t) for t in job_failures]
        job_reports.append(job_entry)
        for mid, stats in per_job.items():
            if mid not in combined:
                combined[mid] = ModelRunStats(
                    model_id=mid,
                    label=stats.label,
                    passes=stats.passes,
                    trials=stats.trials,
                    errors=stats.errors,
                    pass_rate=stats.pass_rate,
                )
            else:
                prev = combined[mid]
                trials = prev.trials + stats.trials
                passes = prev.passes + stats.passes
                errors = prev.errors + stats.errors
                combined[mid] = ModelRunStats(
                    model_id=mid,
                    label=prev.label,
                    passes=passes,
                    trials=trials,
                    errors=errors,
                    pass_rate=(passes / trials) if trials else 0.0,
                )

    verdict = classify_difficulty(combined)
    rates = [s.pass_rate for s in combined.values() if s.trials > 0]
    best_id = max(combined, key=lambda k: combined[k].pass_rate) if combined else None
    worst_id = min(combined, key=lambda k: combined[k].pass_rate) if combined else None

    report: dict[str, Any] = {
        "task_dir": str(task_dir) if task_dir else None,
        "declared_difficulty": declared_difficulty,
        "job_dirs": [str(p) for p in job_dirs],
        "models": {
            mid: {
                "label": s.label,
                "passes": s.passes,
                "trials": s.trials,
                "errors": s.errors,
                "pass_rate": s.pass_rate,
            }
            for mid, s in combined.items()
        },
        "best_model": best_id,
        "worst_model": worst_id,
        "best_pass_rate": max(rates) if rates else None,
        "worst_pass_rate": min(rates) if rates else None,
        "empirical_difficulty": verdict.label,
        "accepted_profile": verdict.accepted,
        "verdict_detail": verdict.detail,
        "per_job": job_reports,
    }
    if include_failures:
        failure_summary = summarize_failures(all_failure_analyses)
        report["failures"] = failure_summary
        report["trials"] = [_analysis_to_dict(t) for t in all_failure_analyses]
    return report


def print_report(report: dict[str, Any]) -> None:
    task = report.get("task_dir") or "(unspecified task)"
    print(f"Task: {task}")
    if report.get("declared_difficulty"):
        print(f"Declared difficulty (task.toml): {report['declared_difficulty']}")
    print(f"Jobs analyzed: {len(report.get('job_dirs') or [])}")
    for job in report.get("job_dirs") or []:
        print(f"  - {job}")
    print()
    print("Pass rates (reward == 1.0):")
    models: dict[str, Any] = report.get("models") or {}
    if not models:
        print("  (no model trials found)")
    else:
        for mid in ("gpt-5.2", "claude-opus-4.6"):
            if mid not in models:
                continue
            m = models[mid]
            print(
                f"  {m['label']}: {m['passes']}/{m['trials']} = "
                f"{_pct(m['pass_rate'])}"
            )
        best = report.get("best_model")
        worst = report.get("worst_model")
        if best and worst and report.get("best_pass_rate") is not None:
            print()
            print(
                f"Best model:  {models[best]['label']} "
                f"({_pct(report['best_pass_rate'])})"
            )
            print(
                f"Worst model: {models[worst]['label']} "
                f"({_pct(report['worst_pass_rate'])})"
            )

    print()
    print(f"Empirical difficulty: {report.get('empirical_difficulty', 'unknown').upper()}")
    print(f"Verdict: {report.get('verdict_detail')}")
    if report.get("declared_difficulty") and report.get("empirical_difficulty"):
        declared = report["declared_difficulty"]
        empirical = report["empirical_difficulty"]
        if declared != empirical:
            print(
                f"Note: task.toml says '{declared}' but empirical band is '{empirical}'."
            )

    failures = report.get("failures")
    if failures:
        print()
        print("Failure quality (from local result.json + verifier artifacts):")
        counts = failures.get("counts") or {}
        print(
            f"  pass={counts.get('pass', 0)}  "
            f"fail-good={counts.get('fail_good', 0)}  "
            f"fail-bad={counts.get('fail_bad', 0)}  "
            f"review={counts.get('review', 0)}"
        )
        print(f"  Difficulty trust: {failures.get('difficulty_trust', 'unknown').upper()}")
        print(f"  {failures.get('difficulty_trust_detail')}")

        trials = report.get("trials") or []
        interesting = [
            t
            for t in trials
            if t.get("outcome") in ("fail_bad", "review", "fail_good")
        ]
        if interesting:
            print()
            print("Per-trial classification:")
            for t in interesting:
                label = {
                    "fail_good": "FAIL-GOOD",
                    "fail_bad": "FAIL-BAD",
                    "review": "REVIEW",
                    "pass": "PASS",
                }.get(str(t.get("outcome")), "?")
                conf = t.get("confidence", "?")
                print(
                    f"  [{label}/{conf}] {t.get('trial_name')}: "
                    f"{t.get('reason')}"
                )
                paths = t.get("review_paths") or []
                if paths:
                    print(f"      review: {', '.join(paths[:4])}")


def print_trial_analysis(analysis: TrialFailureAnalysis) -> None:
    label = {
        "pass": "PASS",
        "fail_good": "FAIL — GOOD (legitimate difficulty)",
        "fail_bad": "FAIL — BAD (task/env/harness issue)",
        "review": "REVIEW (manual check needed)",
    }.get(analysis.outcome, analysis.outcome.upper())
    print(f"Trial: {analysis.trial_name}")
    print(f"Path:  {analysis.trial_dir}")
    if analysis.model_id:
        print(f"Model: {MODELS.get(analysis.model_id, {}).get('label', analysis.model_id)}")
    print(f"Outcome:    {label}")
    print(f"Confidence: {analysis.confidence}")
    print(f"Category:   {analysis.category}")
    print(f"Reason:     {analysis.reason}")
    if analysis.review_paths:
        print("Review:")
        for rel in analysis.review_paths:
            print(f"  - {rel}")


def _find_stb() -> str | None:
    return shutil.which("stb")


def _check_api_env() -> list[str]:
    issues: list[str] = []
    if not os.environ.get("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY is not set")
    base = os.environ.get("OPENAI_BASE_URL", "")
    if base and "portkey" not in base:
        issues.append(
            f"OPENAI_BASE_URL is '{base}' (expected https://api.portkey.ai/v1)"
        )
    elif not base:
        issues.append(
            "OPENAI_BASE_URL is not set (recommended: https://api.portkey.ai/v1)"
        )
    return issues


def _resolve_task_dir(path: str) -> Path:
    task_dir = Path(path).expanduser().resolve()
    if not task_dir.is_dir():
        raise FileNotFoundError(f"task directory not found: {task_dir}")
    if not (task_dir / "task.toml").is_file():
        raise FileNotFoundError(f"missing task.toml in {task_dir}")
    return task_dir


def _job_matches_task(job_dir: Path, task_name: str | None) -> bool:
    if not task_name:
        return True
    config_path = job_dir / "config.json"
    if config_path.is_file():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for task in cfg.get("tasks") or []:
                p = str((task or {}).get("path") or "")
                if task_name in p:
                    return True
        except (OSError, json.JSONDecodeError):
            pass
    for trial in _trial_dirs(job_dir):
        try:
            payload = json.loads((trial / "result.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("task_name") == task_name:
            return True
    return False


def _task_job_dirs(
    jobs_root: Path,
    *,
    task_name: str | None,
    limit: int | None = None,
) -> list[Path]:
    """Recent job directories for a task (oracle/NOP included)."""
    if not jobs_root.is_dir():
        return []

    candidates: list[Path] = []
    for job_dir in sorted(jobs_root.iterdir(), reverse=True):
        if not job_dir.is_dir():
            continue
        if not (job_dir / "result.json").is_file():
            continue
        if not _job_matches_task(job_dir, task_name):
            continue
        candidates.append(job_dir)
        if limit is not None and len(candidates) >= limit:
            break
    return candidates


def _latest_job_dirs(
    jobs_root: Path,
    *,
    task_name: str | None,
    limit: int,
) -> list[Path]:
    if not jobs_root.is_dir():
        return []

    candidates: list[Path] = []
    for job_dir in sorted(jobs_root.iterdir(), reverse=True):
        if not job_dir.is_dir():
            continue
        if not (job_dir / "result.json").is_file():
            continue
        if not _job_matches_task(job_dir, task_name):
            continue

        # Keep jobs that look like frontier agent runs.
        stats = _stats_from_job_result(job_dir) or _stats_from_trials(job_dir)
        if not stats:
            continue
        candidates.append(job_dir)
        if len(candidates) >= limit:
            break

    return candidates


def _report_job_dirs_error(
    *,
    jobs_root: Path,
    task_name: str | None,
    used_latest: bool,
    explicit_dirs: list[Path],
) -> str:
    if explicit_dirs:
        return (
            "No frontier-model trials found in the provided job directories. "
            "agent_test only summarizes GPT-5.2 / Claude Opus runs "
            "(not oracle or NOP Step 2b jobs)."
        )
    task_hint = f" for task {task_name!r}" if task_name else ""
    recent = _task_job_dirs(jobs_root, task_name=task_name, limit=3)
    if used_latest and recent:
        lines = [
            f"No frontier-agent job directories found{task_hint} under {jobs_root}.",
            "Recent jobs exist but are oracle/NOP only — those are skipped for difficulty calibration.",
            "",
            "Run at least one frontier trial, then report again:",
            f"  ./scripts/agent_test.sh run tasks/{task_name} --runs 1",
            "",
            "Or pass an explicit job directory:",
            f"  ./scripts/agent_test.sh report {recent[0]} --task-dir tasks/{task_name}",
        ]
        return "\n".join(lines)
    if used_latest:
        return (
            f"No job directories found{task_hint} under {jobs_root}.\n"
            "Run a frontier-agent calibration job first:\n"
            f"  ./scripts/agent_test.sh run tasks/{task_name or '<task-name>'} --runs 1"
        )
    return (
        "Provide job_dirs and/or --latest with an optional --task filter, "
        "after running ./scripts/agent_test.sh run tasks/<task-name>."
    )


def run_agents(
    task_dir: Path,
    *,
    model_ids: list[str],
    runs: int,
    jobs_dir: Path,
    concurrent: int,
    dry_run: bool,
) -> list[Path]:
    stb = _find_stb()
    if stb is None:
        raise RuntimeError("stb CLI not found on PATH (install snorkelai-stb)")

    env_issues = _check_api_env()
    if env_issues and not dry_run:
        raise RuntimeError(
            "API environment not configured:\n  - " + "\n  - ".join(env_issues)
        )

    created_jobs: list[Path] = []
    task_dir = task_dir.resolve()
    rel_task = os.path.relpath(task_dir, _repo_root())

    for model_id in model_ids:
        spec = MODELS[model_id]
        cmd = [
            stb,
            "harbor",
            "run",
            "-p",
            rel_task,
            "-m",
            spec["harbor_flag"],
            "-k",
            str(runs),
            "-n",
            str(min(concurrent, runs)),
            "-o",
            str(jobs_dir),
            "--quiet",
        ]
        print(f"\n== {spec['label']} ({runs} runs) ==")
        print("$", " ".join(cmd))
        if dry_run:
            continue

        proc = subprocess.run(cmd, cwd=_repo_root(), check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"stb harbor run failed for {spec['label']} (exit {proc.returncode})"
            )

        latest = _latest_job_dirs(jobs_dir, task_name=task_dir.name, limit=1)
        if latest:
            created_jobs.append(latest[0])
            print(f"Job artifacts: {latest[0]}")

    return created_jobs


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frontier agents and calibrate task difficulty from pass rates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run frontier models via stb harbor")
    run_p.add_argument("task_dir", help="Path to task directory (e.g. tasks/my-task)")
    run_p.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Trials per model (default: {DEFAULT_RUNS})",
    )
    run_p.add_argument(
        "--models",
        nargs="+",
        choices=list(MODELS),
        default=list(MODELS),
        metavar="MODEL",
        help="Models to run (default: both)",
    )
    run_p.add_argument(
        "--jobs-dir",
        type=Path,
        default=Path("jobs"),
        help="Harbor jobs output directory (default: jobs)",
    )
    run_p.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Concurrent trials per model job (default: 4)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report after runs",
    )

    report_p = sub.add_parser("report", help="Summarize pass rates from job directories")
    report_p.add_argument(
        "job_dirs",
        nargs="*",
        help="One or more jobs/<timestamp> directories",
    )
    report_p.add_argument(
        "--task-dir",
        type=Path,
        default=None,
        help="Task path (for declared difficulty comparison)",
    )
    report_p.add_argument(
        "--latest",
        action="store_true",
        help="Auto-pick recent frontier-agent jobs",
    )
    report_p.add_argument(
        "--task",
        default=None,
        help="Task name filter with --latest (basename of tasks/<name>)",
    )
    report_p.add_argument(
        "--jobs-root",
        type=Path,
        default=Path("jobs"),
        help="Root directory to scan with --latest (default: jobs)",
    )
    report_p.add_argument(
        "--limit",
        type=int,
        default=2,
        help="How many recent jobs to include with --latest (default: 2)",
    )
    report_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )
    report_p.add_argument(
        "--no-failures",
        action="store_true",
        help="Skip good-fail vs bad-fail classification",
    )

    trial_p = sub.add_parser(
        "trial",
        help="Classify one trial folder (jobs/<job>/<trial>/)",
    )
    trial_p.add_argument(
        "trial_dir",
        help="Path to a single trial directory containing result.json",
    )
    trial_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = _repo_root()

    if args.command == "run":
        try:
            task_dir = _resolve_task_dir(args.task_dir)
        except (FileNotFoundError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        jobs_dir = (repo / args.jobs_dir).resolve()
        jobs_dir.mkdir(parents=True, exist_ok=True)

        try:
            job_dirs = run_agents(
                task_dir,
                model_ids=args.models,
                runs=args.runs,
                jobs_dir=jobs_dir,
                concurrent=args.concurrent,
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            return 0

        if not job_dirs:
            job_dirs = _latest_job_dirs(
                jobs_dir, task_name=task_dir.name, limit=len(args.models)
            )

        report = build_report(
            task_dir=task_dir,
            job_dirs=job_dirs,
            declared_difficulty=_read_task_difficulty(task_dir),
            include_failures=True,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        return 0

    if args.command == "trial":
        trial_dir = Path(args.trial_dir).expanduser().resolve()
        if not (trial_dir / "result.json").is_file():
            print(f"error: no result.json in {trial_dir}", file=sys.stderr)
            return 2
        analysis = classify_trial(trial_dir)
        if args.json:
            print(json.dumps(_analysis_to_dict(analysis), indent=2))
        else:
            print_trial_analysis(analysis)
        return 0

    if args.command == "report":
        job_dirs: list[Path] = [Path(p).expanduser().resolve() for p in args.job_dirs]

        if args.latest:
            task_name = args.task
            if args.task_dir:
                task_name = args.task_dir.name
            scanned = _latest_job_dirs(
                (repo / args.jobs_root).resolve(),
                task_name=task_name,
                limit=args.limit,
            )
            job_dirs.extend(scanned)

        if not job_dirs:
            task_name = args.task
            if args.task_dir:
                task_name = args.task_dir.name
            print(
                "error: "
                + _report_job_dirs_error(
                    jobs_root=(repo / args.jobs_root).resolve(),
                    task_name=task_name,
                    used_latest=bool(args.latest),
                    explicit_dirs=[Path(p) for p in args.job_dirs],
                ),
                file=sys.stderr,
            )
            return 2

        task_dir = args.task_dir
        if task_dir:
            task_dir = task_dir.expanduser().resolve()
        declared = _read_task_difficulty(task_dir) if task_dir else None

        report = build_report(
            task_dir=task_dir,
            job_dirs=job_dirs,
            declared_difficulty=declared,
            include_failures=not args.no_failures,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
