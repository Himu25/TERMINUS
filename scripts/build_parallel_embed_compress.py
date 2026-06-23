#!/usr/bin/env python3
"""Transform copied shard-topk-relay tree into parallel-embed-compress."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "parallel-embed-compress"

REPLACEMENTS: list[tuple[str, str]] = [
    ("topk.lab", "pembed.lab"),
    ("shard-topk-relay", "parallel-embed-compress"),
    ("search_bench", "compress_bench"),
    ("queries_default", "batches_default"),
    ("query_specs", "batch_specs"),
    ("query_id", "batch_id"),
    ("queries_total", "batches_total"),
    ("MeanRecallAt10", "MeanCosineFidelity"),
    ("mean_recall_at_10", "mean_cosine_fidelity"),
    ("MeanNdcgAt10", "MeanCompressRatio"),
    ("mean_ndcg_at_10", "mean_compress_ratio"),
    ("MeanShardUnits", "MeanWorkerUnits"),
    ("mean_shard_units", "mean_worker_units"),
    ("MeanMergeUnits", "MeanSyncUnits"),
    ("mean_merge_units", "mean_sync_units"),
    ("P95QueryUnits", "P95BatchUnits"),
    ("p95_query_units", "p95_batch_units"),
    ("ShardCount", "WorkerCount"),
    ("shard_count", "worker_count"),
    ("ShardUnits", "WorkerUnits"),
    ("shard_units", "worker_units"),
    ("MergeUnits", "SyncUnits"),
    ("merge_units", "sync_units"),
    ("QueryUnits", "BatchUnits"),
    ("query_units", "batch_units"),
    ("ShardsQueried", "WorkersActive"),
    ("shards_queried", "workers_active"),
    ("RecallAt10", "CosineFidelity"),
    ("recall_at_10", "cosine_fidelity"),
    ("NdcgAt10", "CompressRatio"),
    ("ndcg_at_10", "compress_ratio"),
    ("TopIDs", "ChunkIDs"),
    ("top_ids", "chunk_ids"),
    ("GoldHits", "IntactChunks"),
    ("gold_hits", "intact_chunks"),
    ("QueryCase", "BatchCase"),
    ("QueryRow", "BatchRow"),
    ("QueryID", "BatchID"),
    ("dead_shards", "dead_workers"),
    ("DeadShards", "DeadWorkers"),
    ("DeadShardPenalty", "DeadWorkerPenalty"),
    ("recall_floor", "fidelity_floor"),
    ("ndcg_floor", "compress_ratio_floor"),
    ("max_mean_shard_units", "max_mean_worker_units"),
    ("max_mean_merge_units", "max_mean_sync_units"),
    ("max_p95_query_units", "max_p95_batch_units"),
    ("failover_recall_floor", "failover_fidelity_floor"),
    ("tight_security_recall_floor", "tight_pack_fidelity_floor"),
    ("billing_refund_min_recall", "billing_pack_min_fidelity"),
    ("billing_refund_min_gold_hits", "billing_pack_min_intact"),
    ("latency_skew_min_recall", "skew_balance_min_fidelity"),
    ("/app/config/cluster.toml", "/app/config/pipeline.toml"),
    ("cluster.toml", "pipeline.toml"),
    ("lbgen", "refgen"),
    ("LoadQueries", "LoadBatches"),
    ("queries.jsonl", "batches.jsonl"),
    ("q_billing_refund", "b_billing_refund"),
    ("q_cross_billing_ops", "b_cross_billing_ops"),
    ("q_search_ann", "b_search_ann"),
    ("q_failover_shard1", "b_failover_worker1"),
    ("q_failover_shard2", "b_failover_worker2"),
    ("q_failover_multi", "b_failover_multi"),
    ("q_tight_security", "b_tight_security"),
    ("q_latency_skew", "b_latency_skew"),
    ("q_dense_tail", "b_dense_tail"),
    ("q_tight_security", "b_tight_security"),
    ("distributed top-k", "parallel embedding compression"),
    ("top-k search", "embedding compression batch"),
    ("retrieval", "compression"),
    ("relay_policy", "compress_policy"),
]

SKIP_SUFFIXES = {".pyc", ".zip"}


def transform_text(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def process_file(path: Path) -> None:
    if path.suffix in SKIP_SUFFIXES:
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    updated = transform_text(raw)
    if updated != raw:
        path.write_text(updated, encoding="utf-8")


def rename_path(src: Path, dst: Path) -> None:
    if src.exists() and not dst.exists():
        src.rename(dst)


def main() -> None:
    # cmd/lbgen -> cmd/refgen
    lbgen = TASK / "environment" / "cmd" / "lbgen"
    refgen = TASK / "environment" / "cmd" / "refgen"
    if lbgen.is_dir():
        rename_path(lbgen, refgen)

    for path in sorted(TASK.rglob("*")):
        if path.is_file():
            process_file(path)

    # Rename data files if still old names
    data = TASK / "environment" / "data"
    renames = [
        ("queries_default.jsonl", "batches_default.jsonl"),
        ("query_specs.jsonl", "batch_specs.jsonl"),
    ]
    for old, new in renames:
        src, dst = data / old, data / new
        if src.exists() and not dst.exists():
            rename_path(src, dst)

    cfg_old = TASK / "environment" / "config" / "cluster.toml"
    cfg_new = TASK / "environment" / "config" / "pipeline.toml"
    if cfg_old.exists() and not cfg_new.exists():
        rename_path(cfg_old, cfg_new)

    # Update pipeline.toml header comment
    if cfg_new.exists():
        text = cfg_new.read_text(encoding="utf-8")
        text = text.replace(
            "# cluster retrieval guardrails",
            "# parallel compression pipeline guardrails",
        )
        text = text.replace("shard_count", "worker_count")
        cfg_new.write_text(text, encoding="utf-8")

    print("transformed", TASK)


if __name__ == "__main__":
    main()
