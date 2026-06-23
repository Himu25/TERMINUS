#!/usr/bin/env python3
"""One-off authoring helper — lives outside the task tree; not shipped in submissions."""
from __future__ import annotations

import random
import textwrap
from pathlib import Path

TASK = Path(__file__).resolve().parents[1] / "tasks" / "aurora-dossier-compile"
DOSSIER = TASK / "environment" / "data" / "aurora_dossier.md"
WORDLIST = Path("/usr/share/dict/words")


def load_words() -> list[str]:
    raw = WORDLIST.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [w.lower() for w in raw if 4 <= len(w) <= 12 and w.isalpha()]


def build_archive_stream(words: list[str], rng: random.Random, min_chars: int) -> list[str]:
    """Emit paragraphs that consume unique vocabulary without template repetition."""
    pool = list(words)
    rng.shuffle(pool)
    cursor = 0
    parts: list[str] = []
    para_idx = 0

    def next_word() -> str:
        nonlocal cursor, pool
        if cursor >= len(pool):
            pool = list(words)
            rng.shuffle(pool)
            cursor = 0
        word = pool[cursor]
        cursor += 1
        return word

    while sum(len(p) + 1 for p in parts) < min_chars:
        chunk = [next_word() for _ in range(54)]
        sentence_a = " ".join(chunk[:18]).capitalize() + "."
        sentence_b = " ".join(chunk[18:36]).capitalize() + "."
        sentence_c = " ".join(chunk[36:54]).capitalize() + "."
        body = textwrap.fill(f"{sentence_a} {sentence_b} {sentence_c}", width=96)
        parts.append(body)
        parts.append("")
        para_idx += 1
    return parts


def block_body(seq: int, run_name: str, status: str, supersedes: list[int] | None, fields: dict) -> str:
    header = f"<<<DECISION seq={seq} status={status}>>>"
    if supersedes:
        header = f"<<<DECISION seq={seq} status={status} supersedes={','.join(map(str, supersedes))}>>>"
    lines = [header, f"run_name: {run_name}"]
    lines.extend(f"{key}: {val}" for key, val in fields.items())
    lines.append("<<<END>>>")
    return "\n".join(lines)


def main() -> None:
    words = load_words()
    rng = random.Random(17)
    blocks: list[dict] = []
    seq = 1
    approved_runs: dict[int, dict] = {}
    rejected = 0

    while seq <= 95:
        if seq % 7 == 0:
            run = f"aurora-draft-{seq:03d}"
            body = block_body(
                seq,
                run,
                "rejected",
                None,
                {
                    "flavor": "pytorch",
                    "param.lr": "0.050",
                    "param.horizon": "7",
                    "metric.primary": "wape",
                    "metric.secondary": "mape",
                    "lineage.dataset": "demand_v3",
                    "lineage.version": "2024-01-01",
                    "lineage.split": "holdout_a",
                    "gate.min_wape": "0.20",
                    "gate.max_latency_ms": "1200",
                },
            )
            blocks.append({"seq": seq, "status": "rejected", "text": body})
            rejected += 1
            seq += 1
            continue

        if seq % 11 == 0 and approved_runs:
            target_seq = max(approved_runs)
            old = approved_runs[target_seq]
            run = old["run_name"]
            fields = dict(old["fields"])
            fields["param.lr"] = f"0.00{3 + (seq % 5)}"
            fields["param.horizon"] = str(10 + (seq % 6))
            body = block_body(seq, run, "approved", [target_seq], fields)
            blocks.append(
                {
                    "seq": seq,
                    "status": "approved",
                    "supersedes": [target_seq],
                    "text": body,
                    "fields": fields,
                    "run_name": run,
                }
            )
            approved_runs[seq] = {"run_name": run, "fields": fields}
            seq += 1
            continue

        run = f"aurora-run-{seq:03d}"
        fields = {
            "flavor": "pytorch" if seq % 3 else "sklearn",
            "param.lr": f"0.00{1 + (seq % 7)}",
            "param.horizon": str(7 + (seq % 9)),
            "metric.primary": "wape",
            "metric.secondary": "mape",
            "lineage.dataset": "demand_v3",
            "lineage.version": f"2024-{(seq % 12) + 1:02d}-15",
            "lineage.split": "holdout_b" if seq % 2 else "holdout_a",
            "gate.min_wape": f"0.{10 + (seq % 8):02d}",
            "gate.max_latency_ms": str(600 + (seq % 5) * 100),
        }
        body = block_body(seq, run, "approved", None, fields)
        blocks.append({"seq": seq, "status": "approved", "text": body, "fields": fields, "run_name": run})
        approved_runs[seq] = {"run_name": run, "fields": fields}
        seq += 1

    errata = [
        {"seq": 88, "field": "lineage.version", "value": "2024-09-01"},
        {"seq": 72, "field": "lineage.version", "value": "2024-07-01"},
    ]

    parts: list[str] = [
        "# Aurora Demand Forecast — Experiment Dossier",
        "",
        "Compiled notes for the demand council. Only bounded decision markers define MLflow runs.",
        "",
        "## Meeting Notes Archive",
        "",
    ]
    parts.extend(build_archive_stream(words, rng, 210_000))

    parts.extend(["", "## Approved and Rejected Decision Log", ""])
    for item in blocks:
        parts.append(item["text"])
        parts.append("")
        parts.append(build_archive_stream(words, rng, 400)[0])
        parts.append("")

    parts.extend(["", "## Appendix Errata", ""])
    for row in errata:
        parts.append(f"<<<ERRATA seq={row['seq']} field={row['field']} value={row['value']}>>>")

    DOSSIER.write_text("\n".join(parts) + "\n", encoding="utf-8")
    text = DOSSIER.read_text(encoding="utf-8")
    import re

    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    print(
        f"wrote {DOSSIER} ({DOSSIER.stat().st_size} bytes, "
        f"ttr={len(set(tokens))/len(tokens):.3f}, unique={len(set(tokens))})"
    )


if __name__ == "__main__":
    main()
