"""Tests for agent_test.py difficulty reporting."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_test import (
    ModelRunStats,
    _report_job_dirs_error,
    analyze_job_dir,
    build_report,
    classify_difficulty,
    classify_trial,
    main,
    print_report,
)


class AgentTestDifficulty(unittest.TestCase):
    def test_classify_hard_when_worst_model_zero(self) -> None:
        stats = {
            "gpt-5.2": ModelRunStats("gpt-5.2", "GPT-5.2", 2, 5, 0, 0.4),
            "claude-opus-4.6": ModelRunStats(
                "claude-opus-4.6", "Claude Opus 4.6", 0, 5, 0, 0.0
            ),
        }
        verdict = classify_difficulty(stats)
        self.assertEqual(verdict.label, "hard")
        self.assertTrue(verdict.accepted)

    def test_classify_too_easy_above_eighty(self) -> None:
        stats = {
            "gpt-5.2": ModelRunStats("gpt-5.2", "GPT-5.2", 5, 5, 0, 1.0),
            "claude-opus-4.6": ModelRunStats(
                "claude-opus-4.6", "Claude Opus 4.6", 5, 5, 0, 1.0
            ),
        }
        verdict = classify_difficulty(stats)
        self.assertEqual(verdict.label, "too_easy")
        self.assertFalse(verdict.accepted)

    def test_analyze_existing_job(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        job = repo / "jobs" / "2026-05-20__05-13-51"
        if not job.is_dir():
            self.skipTest("sample job directory not present")
        stats = analyze_job_dir(job)
        self.assertIn("gpt-5.2", stats)
        self.assertEqual(stats["gpt-5.2"].passes, 1)
        self.assertEqual(stats["gpt-5.2"].trials, 1)

    def test_classify_verifier_assertion_as_fail_good(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        trial = repo / "jobs" / "2026-05-20__00-30-49" / "transformer-inference-latency__iwc35QX"
        if not trial.is_dir():
            self.skipTest("sample trial not present")
        analysis = classify_trial(trial)
        self.assertEqual(analysis.outcome, "fail_good")
        self.assertIn(analysis.category, ("domain_assertion", "partial_pass"))

    def test_classify_api_error_as_fail_bad(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        trial = repo / "jobs" / "2026-05-20__05-02-30" / "sustained-churn-footprint__ybnJqnm"
        if not trial.is_dir():
            self.skipTest("sample trial not present")
        analysis = classify_trial(trial)
        self.assertEqual(analysis.outcome, "fail_bad")
        self.assertEqual(analysis.category, "infra_api")

    def test_report_latest_oracle_only_gives_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_root = Path(tmp) / "jobs"
            job = jobs_root / "2026-05-21__00-00-00"
            job.mkdir(parents=True)
            (job / "result.json").write_text(
                json.dumps(
                    {
                        "stats": {
                            "evals": {
                                "oracle__adhoc": {
                                    "n_trials": 1,
                                    "n_errors": 0,
                                    "reward_stats": {"reward": {"1.0": ["t1"]}},
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (job / "config.json").write_text(
                json.dumps({"tasks": [{"path": "tasks/catalog-surge-gate"}]}),
                encoding="utf-8",
            )
            msg = _report_job_dirs_error(
                jobs_root=jobs_root,
                task_name="catalog-surge-gate",
                used_latest=True,
                explicit_dirs=[],
            )
            self.assertIn("oracle/NOP", msg)
            self.assertIn("agent_test.sh run", msg)

    def test_main_report_latest_exits_2_when_no_frontier_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_root = Path(tmp) / "jobs"
            job = jobs_root / "2026-05-21__00-00-00"
            job.mkdir(parents=True)
            (job / "result.json").write_text(
                json.dumps(
                    {
                        "stats": {
                            "evals": {
                                "oracle__adhoc": {
                                    "n_trials": 1,
                                    "n_errors": 0,
                                    "reward_stats": {"reward": {"1.0": ["t1"]}},
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (job / "config.json").write_text(
                json.dumps({"tasks": [{"path": "tasks/catalog-surge-gate"}]}),
                encoding="utf-8",
            )
            # Point --jobs-root at our temp tree via chdir is awkward; pass explicit
            # empty list + --latest and rely on jobs_root default — instead invoke
            # helper-only test above. Smoke-test argv parsing with a missing jobs root.
            rc = main(
                [
                    "report",
                    "--latest",
                    "--task",
                    "catalog-surge-gate",
                    "--jobs-root",
                    str(jobs_root),
                ]
            )
            self.assertEqual(rc, 2)

    def test_print_report_survives_zero_completed_trials(self) -> None:
        # Frontier job dirs can exist with n_trials == 0 (cancelled/errored runs).
        report = {
            "task_dir": "/tmp/tasks/session-gate-dashboard",
            "declared_difficulty": "hard",
            "job_dirs": ["/tmp/jobs/2026-05-22__05-53-05"],
            "models": {
                "gpt-5.2": {
                    "label": "GPT-5.2",
                    "passes": 0,
                    "trials": 0,
                    "errors": 1,
                    "pass_rate": 0.0,
                }
            },
            "best_model": "gpt-5.2",
            "worst_model": "gpt-5.2",
            "best_pass_rate": None,
            "worst_pass_rate": None,
            "empirical_difficulty": "unknown",
            "verdict_detail": "No frontier-model trials found in job artifacts.",
        }
        # Must not raise TypeError from _pct(None) when jobs exist but n_trials == 0.
        print_report(report)

    def test_build_report_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            result = {
                "stats": {
                    "evals": {
                        "terminus-2__@openai/gpt-5.2__adhoc": {
                            "n_trials": 5,
                            "n_errors": 0,
                            "reward_stats": {
                                "reward": {
                                    "1.0": ["t1"],
                                    "0.0": ["t2", "t3", "t4", "t5"],
                                }
                            },
                        }
                    }
                }
            }
            (job / "result.json").write_text(json.dumps(result), encoding="utf-8")
            report = build_report(task_dir=None, job_dirs=[job])
            self.assertEqual(report["empirical_difficulty"], "hard")
            self.assertEqual(report["models"]["gpt-5.2"]["passes"], 1)


if __name__ == "__main__":
    unittest.main()
