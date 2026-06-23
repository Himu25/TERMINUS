from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import dockerfile_check

REPO_ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER_TASK = REPO_ROOT / "tasks" / "classifier-robustness-gate"
RANK_SPIKE_TASK = REPO_ROOT / "tasks" / "rank-spike-remediation"
TENSOR_RETENTION_TASK = REPO_ROOT / "tasks" / "tensor-retention-gate"
TRANSFORMER_LATENCY_TASK = REPO_ROOT / "tasks" / "transformer-inference-latency"
ANN_FOOTPRINT_TASK = REPO_ROOT / "tasks" / "ann-footprint-gate"
CLUSTER_RECOVERY_TASK = REPO_ROOT / "tasks" / "cluster-recovery-gate"
SESSION_GATE_DASHBOARD_TASK = REPO_ROOT / "tasks" / "session-gate-dashboard"
CV_DATASET_REPAIR_TASK = REPO_ROOT / "tasks" / "cv-dataset-repair"
BUSINESS_KPI_DRIFT_TASK = REPO_ROOT / "tasks" / "business-kpi-drift"
GROUNDED_CONTEXT_BENCH_TASK = REPO_ROOT / "tasks" / "grounded-context-bench"
ANN_QUERY_SCHEDULER_TASK = REPO_ROOT / "tasks" / "ann-query-scheduler"
ANN_INCREMENTAL_REINDEX_TASK = REPO_ROOT / "tasks" / "ann-incremental-reindex"
SEMANTIC_SEARCH_RECOVERY_TASK = REPO_ROOT / "tasks" / "semantic-search-recovery"
PARALLEL_EMBED_COMPRESS_TASK = REPO_ROOT / "tasks" / "parallel-embed-compress"
FAISS_INDEX_REGRESSION_TASK = REPO_ROOT / "tasks" / "faiss-index-regression"
HYBRID_SEARCH_LATENCY_TASK = REPO_ROOT / "tasks" / "hybrid-search-latency"
TOKENIZER_REGRESSION_TASK = REPO_ROOT / "tasks" / "tokenizer-regression-reproduction"
LABEL_NOISE_TASK = REPO_ROOT / "tasks" / "label-noise-isolation"
LORA_VRAM_TASK = REPO_ROOT / "tasks" / "lora-vram-pipeline"
CROSS_SERVICE_EMBEDDING_MISMATCH_TASK = REPO_ROOT / "tasks" / "cross-service-embedding-mismatch"


def write_minimal_task(
    root: Path,
    *,
    dockerfile: str,
    task_toml: str | None = None,
    dockerignore: str | None = None,
) -> Path:
    task_dir = root / "sample-task"
    env = task_dir / "environment"
    env.mkdir(parents=True)
    (env / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    if dockerignore is not None:
        (env / ".dockerignore").write_text(dockerignore, encoding="utf-8")
    default_toml = """
version = "2.0"

[metadata]
author_name = "anonymous"
author_email = "anonymous"
difficulty = "hard"
category = "software-engineering"
subcategories = []
codebase_size = "small"
number_of_milestones = 0
languages = ["python"]
tags = ["a", "b", "c"]
expert_time_estimate_min = 30
junior_time_estimate_min = 120

[agent]
timeout_sec = 900

[verifier]
timeout_sec = 300

[environment]
allow_internet = false
build_timeout_sec = 600
cpus = 1
memory_mb = 2048
storage_mb = 10240
"""
    (task_dir / "task.toml").write_text(task_toml or default_toml, encoding="utf-8")
    return task_dir


GOOD_DOCKERFILE = """\
FROM python:3.13-slim-bookworm@sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789

LABEL org.opencontainers.image.source="https://example.com/task"
LABEL org.opencontainers.image.revision="deadbeef"

WORKDIR /app

RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        tmux=3.3a-3 \\
        asciinema=2.2.0-1 \\
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir pytest==8.4.1

COPY src/ /app/src/
"""


class DockerfileCheckTest(unittest.TestCase):
    def test_compliant_task_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=GOOD_DOCKERFILE)
            report = dockerfile_check.build_report(task_dir)
        self.assertEqual(report["fails"], 0)
        self.assertEqual(dockerfile_check.exit_code(report), 0)

    def test_missing_digest_fails(self) -> None:
        bad = GOOD_DOCKERFILE.replace("@sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789", "")
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=bad)
            report = dockerfile_check.build_report(task_dir)
        self.assertGreater(report["fails"], 0)
        messages = json.dumps(report)
        self.assertIn("pin_base_digest", messages)
        self.assertIn("@sha256", messages)

    def test_missing_session_tools_fails(self) -> None:
        bad = GOOD_DOCKERFILE.replace("tmux=3.3a-3 \\\n        asciinema=2.2.0-1 \\\n", "")
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=bad)
            report = dockerfile_check.build_report(task_dir)
        self.assertGreater(report["fails"], 0)
        self.assertIn("agent_session_tools", json.dumps(report))

    def test_copy_solution_fails(self) -> None:
        bad = GOOD_DOCKERFILE + "\nCOPY solution/ /app/solution/\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=bad)
            report = dockerfile_check.build_report(task_dir)
        self.assertGreater(report["fails"], 0)
        self.assertIn("solution/", json.dumps(report))

    def test_allow_internet_must_be_false(self) -> None:
        toml = """
version = "2.0"
[environment]
allow_internet = true
build_timeout_sec = 600
cpus = 1
memory_mb = 2048
storage_mb = 10240
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=GOOD_DOCKERFILE, task_toml=toml)
            report = dockerfile_check.build_report(task_dir)
        self.assertGreater(report["fails"], 0)
        self.assertIn("allow_internet", json.dumps(report))

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = write_minimal_task(Path(tmpdir), dockerfile=GOOD_DOCKERFILE)
            exit_code = dockerfile_check.main([str(task_dir), "--json"])
        self.assertEqual(exit_code, 0)

    def test_classifier_robustness_gate_task_passes(self) -> None:
        if not CLASSIFIER_TASK.is_dir():
            self.skipTest("classifier-robustness-gate task directory is not present")
        report = dockerfile_check.build_report(CLASSIFIER_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        # WARN-only (exit 2) is acceptable for real tasks missing optional .dockerignore/OCI labels.
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_rank_spike_remediation_task_passes(self) -> None:
        if not RANK_SPIKE_TASK.is_dir():
            self.skipTest("rank-spike-remediation task directory is not present")
        report = dockerfile_check.build_report(RANK_SPIKE_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_tensor_retention_gate_task_passes(self) -> None:
        if not TENSOR_RETENTION_TASK.is_dir():
            self.skipTest("tensor-retention-gate task directory is not present")
        report = dockerfile_check.build_report(TENSOR_RETENTION_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_transformer_inference_latency_task_passes(self) -> None:
        if not TRANSFORMER_LATENCY_TASK.is_dir():
            self.skipTest("transformer-inference-latency task directory is not present")
        report = dockerfile_check.build_report(TRANSFORMER_LATENCY_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_ann_footprint_gate_task_passes(self) -> None:
        if not ANN_FOOTPRINT_TASK.is_dir():
            self.skipTest("ann-footprint-gate task directory is not present")
        report = dockerfile_check.build_report(ANN_FOOTPRINT_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_cluster_recovery_gate_task_passes(self) -> None:
        if not CLUSTER_RECOVERY_TASK.is_dir():
            self.skipTest("cluster-recovery-gate task directory is not present")
        report = dockerfile_check.build_report(CLUSTER_RECOVERY_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_session_gate_dashboard_task_passes(self) -> None:
        if not SESSION_GATE_DASHBOARD_TASK.is_dir():
            self.skipTest("session-gate-dashboard task directory is not present")
        report = dockerfile_check.build_report(SESSION_GATE_DASHBOARD_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_cv_dataset_repair_task_passes(self) -> None:
        if not CV_DATASET_REPAIR_TASK.is_dir():
            self.skipTest("cv-dataset-repair task directory is not present")
        report = dockerfile_check.build_report(CV_DATASET_REPAIR_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_business_kpi_drift_task_passes(self) -> None:
        if not BUSINESS_KPI_DRIFT_TASK.is_dir():
            self.skipTest("business-kpi-drift task directory is not present")
        report = dockerfile_check.build_report(BUSINESS_KPI_DRIFT_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_grounded_context_bench_task_passes(self) -> None:
        if not GROUNDED_CONTEXT_BENCH_TASK.is_dir():
            self.skipTest("grounded-context-bench task directory is not present")
        report = dockerfile_check.build_report(GROUNDED_CONTEXT_BENCH_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_ann_query_scheduler_task_passes(self) -> None:
        if not ANN_QUERY_SCHEDULER_TASK.is_dir():
            self.skipTest("ann-query-scheduler task directory is not present")
        report = dockerfile_check.build_report(ANN_QUERY_SCHEDULER_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_ann_incremental_reindex_task_passes(self) -> None:
        if not ANN_INCREMENTAL_REINDEX_TASK.is_dir():
            self.skipTest("ann-incremental-reindex task directory is not present")
        report = dockerfile_check.build_report(ANN_INCREMENTAL_REINDEX_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_semantic_search_recovery_task_passes(self) -> None:
        if not SEMANTIC_SEARCH_RECOVERY_TASK.is_dir():
            self.skipTest("semantic-search-recovery task directory is not present")
        report = dockerfile_check.build_report(SEMANTIC_SEARCH_RECOVERY_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_parallel_embed_compress_task_passes(self) -> None:
        if not PARALLEL_EMBED_COMPRESS_TASK.is_dir():
            self.skipTest("parallel-embed-compress task directory is not present")
        report = dockerfile_check.build_report(PARALLEL_EMBED_COMPRESS_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_faiss_index_regression_task_passes(self) -> None:
        if not FAISS_INDEX_REGRESSION_TASK.is_dir():
            self.skipTest("faiss-index-regression task directory is not present")
        report = dockerfile_check.build_report(FAISS_INDEX_REGRESSION_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_hybrid_search_latency_task_passes(self) -> None:
        if not HYBRID_SEARCH_LATENCY_TASK.is_dir():
            self.skipTest("hybrid-search-latency task directory is not present")
        report = dockerfile_check.build_report(HYBRID_SEARCH_LATENCY_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_tokenizer_regression_reproduction_task_passes(self) -> None:
        if not TOKENIZER_REGRESSION_TASK.is_dir():
            self.skipTest("tokenizer-regression-reproduction task directory is not present")
        report = dockerfile_check.build_report(TOKENIZER_REGRESSION_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_label_noise_isolation_task_passes(self) -> None:
        if not LABEL_NOISE_TASK.is_dir():
            self.skipTest("label-noise-isolation task directory is not present")
        report = dockerfile_check.build_report(LABEL_NOISE_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_lora_vram_pipeline_task_passes(self) -> None:
        if not LORA_VRAM_TASK.is_dir():
            self.skipTest("lora-vram-pipeline task directory is not present")
        report = dockerfile_check.build_report(LORA_VRAM_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))

    def test_cross_service_embedding_mismatch_task_passes(self) -> None:
        if not CROSS_SERVICE_EMBEDDING_MISMATCH_TASK.is_dir():
            self.skipTest("cross-service-embedding-mismatch task directory is not present")
        report = dockerfile_check.build_report(CROSS_SERVICE_EMBEDDING_MISMATCH_TASK)
        self.assertEqual(
            report["fails"],
            0,
            json.dumps(report["results"], indent=2),
        )
        self.assertIn(dockerfile_check.exit_code(report), (0, 2))


if __name__ == "__main__":
    unittest.main()
