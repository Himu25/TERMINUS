#!/usr/bin/env python3
"""One-shot scaffold for tasks/regional-experiment-contamination."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tasks" / "regional-experiment-contamination"
ENV = ROOT / "environment"
TESTS = ROOT / "tests"


def w(rel: str, content: str, mode: int = 0o644) -> None:
    p = ROOT / rel if not rel.startswith("environment") else ROOT / rel
    if rel.startswith("environment/"):
        p = ENV / rel[len("environment/") :]
    elif rel.startswith("tests/"):
        p = TESTS / rel[len("tests/") :]
    else:
        p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    if "build.sh" in str(p) or "solve.sh" in str(p) or "/scripts/" in str(p):
        p.chmod(0o755)


def pack_fixture(name: str, users: list[dict], regions: list[str]) -> None:
    base = TESTS / "fixtures" / name
    base.mkdir(parents=True, exist_ok=True)
    pack = {
        "run_id": name,
        "experiment_id": "exp_main",
        "salt": "bench_salt_v3",
        "regions": regions,
        "buckets": 2,
    }
    (base / "experiment_pack.json").write_text(json.dumps(pack, indent=2) + "\n")
    for reg in regions:
        d = base / "regions" / reg
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        for u in users:
            if reg in u.get("regions", regions):
                lines.append(
                    {
                        "user_id": u["user_id"],
                        "converted": u.get("converted", {}).get(reg, 0),
                    }
                )
        (d / "exposures.jsonl").write_text(
            "\n".join(json.dumps(x) for x in lines) + ("\n" if lines else "")
        )


# --- fixtures data ---
pack_alpha_users = [
    {"user_id": "u01", "regions": ["eu-west"], "converted": {"eu-west": 1}},
    {"user_id": "u02", "regions": ["eu-west"], "converted": {"eu-west": 0}},
    {"user_id": "u03", "regions": ["eu-west"], "converted": {"eu-west": 1}},
    {"user_id": "u04", "regions": ["eu-west"], "converted": {"eu-west": 0}},
    {"user_id": "u05", "regions": ["eu-west"], "converted": {"eu-west": 0}},
]

pack_cross_users = [
    {"user_id": "traveler_a", "regions": ["eu-west", "us-east"], "converted": {"eu-west": 1, "us-east": 0}},
    {"user_id": "traveler_b", "regions": ["eu-west", "us-east"], "converted": {"eu-west": 0, "us-east": 1}},
    {"user_id": "local_eu_1", "regions": ["eu-west"], "converted": {"eu-west": 1}},
    {"user_id": "local_eu_2", "regions": ["eu-west"], "converted": {"eu-west": 0}},
    {"user_id": "local_us_1", "regions": ["us-east"], "converted": {"us-east": 1}},
    {"user_id": "local_us_2", "regions": ["us-east"], "converted": {"us-east": 0}},
]

pack_beta_users = pack_alpha_users + [
    {"user_id": "u06", "regions": ["ap-south"], "converted": {"ap-south": 1}},
    {"user_id": "u07", "regions": ["ap-south"], "converted": {"ap-south": 0}},
]

pack_gamma_users = pack_cross_users + [
    {"user_id": "local_ap_1", "regions": ["ap-south"], "converted": {"ap-south": 1}},
    {"user_id": "local_ap_2", "regions": ["ap-south"], "converted": {"ap-south": 0}},
]

pack_delta_users = [
    {"user_id": f"du_{i:02d}", "regions": ["eu-west", "us-east", "ap-south"], "converted": {r: i % 2 for r in ["eu-west", "us-east", "ap-south"]}}
    for i in range(1, 9)
]

for nm, users, regs in [
    ("pack_alpha", pack_alpha_users, ["eu-west"]),
    ("pack_beta", pack_beta_users, ["eu-west", "ap-south"]),
    ("pack_gamma", pack_gamma_users, ["eu-west", "us-east", "ap-south"]),
    ("pack_cross_region", pack_cross_users, ["eu-west", "us-east"]),
    ("pack_delta", pack_delta_users, ["eu-west", "us-east", "ap-south"]),
]:
    pack_fixture(nm, users, regs)

# copy active from alpha
import shutil

active = ENV / "data" / "active"
if active.exists():
    shutil.rmtree(active)
shutil.copytree(TESTS / "fixtures" / "pack_alpha", active)

print("fixtures ok", ROOT)
