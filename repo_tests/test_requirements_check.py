"""Tests for requirements_check.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import requirements_check

REPO_ROOT = Path(__file__).resolve().parents[1]
CLUSTER_TASK = REPO_ROOT / "tasks" / "cluster-recovery-gate"
BUSINESS_KPI_DRIFT_TASK = REPO_ROOT / "tasks" / "business-kpi-drift"
GROUNDED_CONTEXT_BENCH_TASK = REPO_ROOT / "tasks" / "grounded-context-bench"


class RequirementsCheckCliTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        proc = subprocess.run(
            ["python3", str(REPO_ROOT / "requirements_check.py"), "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("submission requirements", proc.stdout)

    def test_missing_task_dir_exits_nonzero(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "requirements_check.py"),
                "tasks/__does_not_exist__",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)

    @unittest.skipUnless(CLUSTER_TASK.is_dir(), "fixture task missing")
    def test_json_output_has_checks(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "requirements_check.py"),
                str(CLUSTER_TASK),
                "--quick",
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(proc.returncode, (0, 1, 2))
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["task"], "cluster-recovery-gate")
        self.assertGreater(len(payload["checks"]), 5)

    @unittest.skipUnless(BUSINESS_KPI_DRIFT_TASK.is_dir(), "fixture task missing")
    def test_business_kpi_drift_automated_checks_no_fail(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "requirements_check.py"),
                str(BUSINESS_KPI_DRIFT_TASK),
                "--quick",
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(proc.returncode, (0, 2), proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["task"], "business-kpi-drift")
        fails = [c for c in payload["checks"] if c["status"] == "fail"]
        self.assertEqual(fails, [], json.dumps(fails, indent=2))

    @unittest.skipUnless(GROUNDED_CONTEXT_BENCH_TASK.is_dir(), "fixture task missing")
    def test_grounded_context_bench_automated_checks_no_fail(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "requirements_check.py"),
                str(GROUNDED_CONTEXT_BENCH_TASK),
                "--quick",
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(proc.returncode, (0, 2), proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["task"], "grounded-context-bench")
        fails = [c for c in payload["checks"] if c["status"] == "fail"]
        self.assertEqual(fails, [], json.dumps(fails, indent=2))


class RequirementsCheckUnitTests(unittest.TestCase):
    def test_packaging_forbidden_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sample"
            root.mkdir()
            (root / "rubric.txt").write_text("x", encoding="utf-8")
            report = requirements_check.Report(task_dir=root, task_name="sample")
            requirements_check.check_packaging_hygiene(report, root)
            statuses = [c.status for c in report.checks]
            self.assertIn(requirements_check.Status.WARN, statuses)

    def test_resolve_task_dir_relative(self) -> None:
        path = requirements_check.resolve_task_dir("tasks/cluster-recovery-gate")
        self.assertTrue(path.is_absolute())
        self.assertTrue(str(path).endswith("cluster-recovery-gate"))

    def test_legacy_canary_fails_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sample"
            root.mkdir()
            (root / "instruction.md").write_text("harbor-canary GUID abc\n", encoding="utf-8")
            report = requirements_check.Report(task_dir=root, task_name="sample")
            requirements_check.check_legacy_canary_policy(report, root)
            self.assertTrue(any(c.status == requirements_check.Status.FAIL for c in report.checks))


if __name__ == "__main__":
    unittest.main()
