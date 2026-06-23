#!/usr/bin/env python3
"""One-shot generator for tasks/flag-rollout-recovery (authoring tool, not shipped)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "flag-rollout-recovery"
SWARM = ROOT / "tasks" / "swarm-mesh-coord-heal"
SWARM_FIX = SWARM / "tests" / "fixtures"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def convert_swarm_fixture(src_name: str, dst_name: str) -> None:
    src = SWARM_FIX / src_name
    dst = TASK / "tests" / "fixtures" / dst_name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    pack_path = dst / "swarm_pack.json"
    plan = json.loads(pack_path.read_text())
    mesh = {
        "plan_id": plan["pack_id"],
        "flag_key": "checkout_flow",
        "target_ver": plan.get("target_ver", 2),
        "rollback_ver": 1,
        "q_size": plan["q_size"],
        "sep_seq": plan["sep_epoch"],
        "prop_tight_ms": plan["link_tight_ms"],
        "service_total": 50,
        "regions": [f"r{i}" for i in range(1, 6)],
    }
    pack_path.unlink()
    w(dst / "mesh_plan.json", json.dumps(mesh, indent=2) + "\n")
    units = dst / "units"
    regions = dst / "regions"
    regions.mkdir()
    unit_dirs = sorted(units.iterdir())
    for idx, udir in enumerate(unit_dirs[:5]):
        rid = f"r{idx + 1}"
        rdir = regions / rid
        rdir.mkdir()
        meta = json.loads((udir / "meta.json").read_text())
        region_meta = {
            "region_id": rid,
            "clock_skew_ms": meta["clock_skew_ms"],
            "prop_lag_ms": meta.get("radio_hold_ms", 0),
            "stale_mark": meta["stale_mark"],
            "service_ids": [f"s{idx * 10 + j + 1:02d}" for j in range(10)],
        }
        w(rdir / "region_meta.json", json.dumps(region_meta, indent=2) + "\n")
        seg = udir / "seg_001.jsonl"
        if seg.exists():
            lines = []
            for line in seg.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                lines.append(
                    json.dumps(
                        {
                            "rollout_seq": row["seq"],
                            "ver": row["epoch"],
                            "observed_ms": row["gps_ms"],
                            "service_id": row["payload"],
                            "crc": row["crc"],
                            "region": rid,
                        }
                    )
                )
            w(rdir / "shard_001.jsonl", "\n".join(lines) + "\n")
    shutil.rmtree(units)


def main() -> None:
    if TASK.exists():
        shutil.rmtree(TASK)
    TASK.mkdir()

    # --- metadata ---
    w(
        TASK / "task.toml",
        """version = "2.0"

[metadata]
author_name = "anonymous"
author_email = "anonymous"
difficulty = "hard"
category = "software-engineering"
subcategories = ["tool_specific"]
number_of_milestones = 0
codebase_size = "small"
languages = ["rust", "go", "bash"]
tags = ["distributed-systems", "feature-flags", "rollout", "go", "rust", "recovery"]
expert_time_estimate_min = 45
junior_time_estimate_min = 150

[agent]
timeout_sec = 1800

[verifier]
timeout_sec = 900

[environment]
allow_internet = false
build_timeout_sec = 600
cpus = 2
memory_mb = 4096
storage_mb = 10240
""",
    )

    w(
        TASK / "instruction.md",
        """A bad control-plane push left fifty simulated services across five regional shards serving mixed flag versions after a partial deployment. Rollout history under `/app/data` shows some shards still on the prior version, edge caches lag the control plane, propagation delay skews observed adoption times, and a stalled rollback left pockets on the wrong version. Uptime must stay up while state is repaired.

The recovery driver at `/app/bin/flag_recover` reads `/app/data/active/mesh_plan.json` and regional shard trees under `/app/data/active/regions/`, but it folds cache watermarks from the wrong extreme, under-counts regional quorum for admitted versions, mishandles propagation lag when ordering observations, and writes `/app/output/rollout_report.json` with incorrect converge totals.

Repair the Go and Rust sources under `/app`, rebuild with `/app/scripts/build.sh`, run the driver with `TB_FLAG_FIXTURE=1`, and leave `/app/output/rollout_report.json` matching deterministic replay of the active mesh plan. Field meanings for the outward JSON (`schema_version`, `plan_id`, `adopted_ver`, `converge_seq`, `stale_cache_repairs`, `propagation_gaps`, `services_up`, `revert_count`, `keep_count`, `prop_band`, `rollback_clean`, `digest_hex`) are documented in the comment above main in `/app/cmd/flag_recover/main.go`. Go unit tests under `/app` must pass. Signal completion once the bundled active plan replays to a matching report.
""",
    )

    w(
        TASK / "output_contract.toml",
        """user_visible_outputs = [
  "/app/output/rollout_report.json",
  "/app/bin/flag_recover",
  "/app/scripts/build.sh",
]

internal_harness_files = [
  "/app/internal/driver",
  "/app/internal/engine",
  "/app/cachegate",
]

[structured_outputs.rollout_report]
target = "/app/output/rollout_report.json"
format = "json"
instruction_checks = [
  "schema_version",
  "plan_id",
  "adopted_ver",
  "converge_seq",
  "stale_cache_repairs",
  "propagation_gaps",
  "services_up",
  "revert_count",
  "keep_count",
  "prop_band",
  "rollback_clean",
  "digest_hex",
]
""",
    )

    # --- go module ---
    w(
        TASK / "environment" / "go.mod",
        """module lab.local/flag_rollout_recovery

go 1.22
""",
    )

    w(
        TASK / "environment" / "cmd" / "flag_recover" / "main.go",
        """// Report JSON for /app/output/rollout_report.json:
//
// schema_version — string, must be "1"
// plan_id — string, echoes active mesh plan name
// adopted_ver — uint32, highest version in the consistent adoption chain
// converge_seq — highest contiguous rollout step included in the chain
// stale_cache_repairs — cache generation fixes applied during heal
// propagation_gaps — rollout steps without regional quorum agreement
// services_up — count of regional shards contributing to accepted rows
// revert_count — shards assigned rollback version after partial heal
// keep_count — shards kept on target version
// prop_band — string, "tight" or "wide"
// rollback_clean — boolean (not 0/1 strings)
// digest_hex — lowercase hex SHA-256 of plan_id|adopted_ver|converge_seq|stale_cache_repairs|propagation_gaps|services_up|revert_count|keep_count|prop_band|rollback_clean
//
// Root object contains only these keys.
package main

import (
	"log"
	"os"

	"lab.local/flag_rollout_recovery/internal/driver"
)

func main() {
	if os.Getenv("TB_FLAG_FIXTURE") != "1" {
		log.Fatal("TB_FLAG_FIXTURE unset or not 1")
	}
	rep, err := driver.RunActive("/app")
	if err != nil {
		log.Fatal(err)
	}
	if err := driver.EmitReport("/app/output/rollout_report.json", rep); err != nil {
		log.Fatal(err)
	}
}
""",
    )

    go_files = {
        "pkg/frame/entry.go": """package frame

// Row is one append-only shard line from a regional segment.
type Row struct {
	RolloutSeq uint32 `json:"rollout_seq"`
	Ver        uint32 `json:"ver"`
	WallMS     int64  `json:"observed_ms"`
	ServiceID  string `json:"service_id"`
	CRC        uint16 `json:"crc"`
	Region     string `json:"region"`
}
""",
        "pkg/region/unit.go": """package region

// Profile is regional shard metadata.
type Profile struct {
	RegionID     string   `json:"region_id"`
	ClockSkewMS  int64    `json:"clock_skew_ms"`
	PropLagMS    int64    `json:"prop_lag_ms"`
	StaleMark    uint32   `json:"stale_mark"`
	ServiceIDs   []string `json:"service_ids"`
}
""",
        "pkg/frame/crc.go": """package frame

// WireCRC folds rollout step, service id, and version into a 16-bit tag.
func WireCRC(seq uint32, serviceID string, ver uint32) uint16 {
	payload := serviceID
	s := uint32(0)
	for _, b := range []byte(payload) {
		s += uint32(b)
	}
	s ^= seq ^ ver
	return uint16(s & 0xFFFF)
}
""",
        "pkg/offsetfold/fold.go": """package offsetfold

import "lab.local/flag_rollout_recovery/cachegate"

// FoldRegionSkew applies optional propagation lag smear to the recorded clock skew baseline.
func FoldRegionSkew(skewMS int64, propLagMS int64) int64 {
	return cachegate.ApplyLag(skewMS, propLagMS)
}
""",
        "pkg/quorumgate/op_q.go": """package quorumgate

// OpQ decides whether enough regional shards reported the same version group.
func OpQ(shardCount int, need int) bool {
	_ = need
	return shardCount >= 1
}
""",
        "pkg/cachefold/op_w.go": """package cachefold

// OpW folds regional stale marks into one replay watermark.
func OpW(marks []int64) int64 {
	if len(marks) == 0 {
		return 0
	}
	best := marks[0]
	for _, m := range marks[1:] {
		if m > best {
			best = m
		}
	}
	return best
}
""",
        "pkg/timenorm/op_t.go": """package timenorm

// OpT adjusts wall time for drift comparisons.
func OpT(wall int64, offset int64) int64 {
	return wall + offset
}
""",
        "pkg/version/info.go": """package version

// Tool identifies the recovery driver build.
const Tool = "flag_recover"
""",
        "internal/vercheck/op_v.go": """package vercheck

import "lab.local/flag_rollout_recovery/pkg/frame"

// op_v checks the stored integrity tag against shard bytes.
func op_v(seq uint32, serviceID string, ver uint32, stored uint16) bool {
	_ = seq
	_ = ver
	return uint16(len(serviceID)&0xFFFF) == stored
}

// OpValid is the exported integrity gate.
func OpValid(seq uint32, serviceID string, ver uint32, stored uint16) bool {
	return op_v(seq, serviceID, ver, stored)
}

func wireMatch(seq uint32, serviceID string, ver uint32, stored uint16) bool {
	want := frame.WireCRC(seq, serviceID, ver)
	return want == stored
}
""",
        "internal/freeze/pick.go": """package freeze

import (
	"lab.local/flag_rollout_recovery/pkg/cachefold"
	"lab.local/flag_rollout_recovery/pkg/region"
)

// Watermark collects partition marks from regional profiles.
func Watermark(profiles []region.Profile) int64 {
	marks := make([]int64, 0, len(profiles))
	for _, p := range profiles {
		marks = append(marks, int64(p.StaleMark))
	}
	return cachefold.OpW(marks)
}
""",
        "internal/skew/adjust.go": """package skew

import (
	"lab.local/flag_rollout_recovery/pkg/frame"
	"lab.local/flag_rollout_recovery/pkg/timenorm"
)

// AdjustWall normalizes observed time for a shard row.
func AdjustWall(row frame.Row, offset int64) int64 {
	return timenorm.OpT(row.WallMS, offset)
}
""",
        "internal/config/defaults.json": json.dumps({"replay_mode": "active"}, indent=2) + "\n",
        "internal/config/load.go": """package config

import (
	"encoding/json"
	"os"
	"path/filepath"

	"lab.local/flag_rollout_recovery/pkg/frame"
	"lab.local/flag_rollout_recovery/pkg/offsetfold"
	"lab.local/flag_rollout_recovery/pkg/region"
)

// Plan describes one recovery scenario root.
type Plan struct {
	PlanID        string   `json:"plan_id"`
	FlagKey       string   `json:"flag_key"`
	TargetVer     uint32   `json:"target_ver"`
	RollbackVer   uint32   `json:"rollback_ver"`
	QSize         int      `json:"q_size"`
	SepSeq        uint32   `json:"sep_seq"`
	PropTightMS   int64    `json:"prop_tight_ms"`
	ServiceTotal  int      `json:"service_total"`
	Regions       []string `json:"regions"`
}

// ActivePaths resolves the bundled active plan directory.
func ActivePaths(root string) (string, error) {
	return filepath.Join(root, "data", "active"), nil
}

// LoadPlan reads mesh_plan.json and regional shard trees.
func LoadPlan(dir string) (Plan, []region.Profile, map[uint32][]frame.Row, map[string]int64, error) {
	raw, err := os.ReadFile(filepath.Join(dir, "mesh_plan.json"))
	if err != nil {
		return Plan{}, nil, nil, nil, err
	}
	var doc Plan
	if err := json.Unmarshal(raw, &doc); err != nil {
		return Plan{}, nil, nil, nil, err
	}
	profiles := make([]region.Profile, 0, len(doc.Regions))
	offsets := make(map[string]int64, len(doc.Regions))
	rows := make(map[uint32][]frame.Row)
	for _, rid := range doc.Regions {
		metaPath := filepath.Join(dir, "regions", rid, "region_meta.json")
		metaRaw, err := os.ReadFile(metaPath)
		if err != nil {
			return Plan{}, nil, nil, nil, err
		}
		var prof region.Profile
		if err := json.Unmarshal(metaRaw, &prof); err != nil {
			return Plan{}, nil, nil, nil, err
		}
		profiles = append(profiles, prof)
		offsets[rid] = offsetfold.FoldRegionSkew(prof.ClockSkewMS, prof.PropLagMS)
		seg := filepath.Join(dir, "regions", rid, "shard_001.jsonl")
		data, err := os.ReadFile(seg)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return Plan{}, nil, nil, nil, err
		}
		for _, line := range splitLines(string(data)) {
			if line == "" {
				continue
			}
			var row frame.Row
			if err := json.Unmarshal([]byte(line), &row); err != nil {
				continue
			}
			row.Region = rid
			rows[row.RolloutSeq] = append(rows[row.RolloutSeq], row)
		}
	}
	return doc, profiles, rows, offsets, nil
}

func splitLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}
""",
        "internal/engine/recover.go": """package engine

import (
	"lab.local/flag_rollout_recovery/internal/freeze"
	"lab.local/flag_rollout_recovery/internal/merge"
	"lab.local/flag_rollout_recovery/pkg/frame"
	"lab.local/flag_rollout_recovery/pkg/region"
)

// Replay executes one plan through freeze and merge stages.
func Replay(
	planID string,
	qSize int,
	sepSeq uint32,
	propTight int64,
	targetVer uint32,
	rollbackVer uint32,
	profiles []region.Profile,
	allRows map[uint32][]frame.Row,
	offsets map[string]int64,
) merge.Outcome {
	wm := freeze.Watermark(profiles)
	above := make(map[uint32][]frame.Row)
	for seq, rows := range allRows {
		if seq > uint32(wm) {
			above[seq] = rows
		}
	}
	out := merge.FusePlan(uint32(wm), qSize, sepSeq, propTight, targetVer, rollbackVer, offsets, above, allRows)
	_ = planID
	return out
}
""",
        "internal/merge/fuse.go": """package merge

import (
	"lab.local/flag_rollout_recovery/internal/skew"
	"lab.local/flag_rollout_recovery/internal/vercheck"
	"lab.local/flag_rollout_recovery/pkg/frame"
	"lab.local/flag_rollout_recovery/pkg/quorumgate"
)

// Outcome is the folded recovery counters for one plan replay.
type Outcome struct {
	AdoptedVer          uint32
	ConvergeSeq         uint32
	StaleCacheRepairs   uint32
	PropagationGaps     uint32
	ServicesUp          uint32
	RevertCount         uint32
	KeepCount           uint32
	PropBand            string
	RollbackClean       bool
}

// FusePlan rebuilds consistent rollout state above a watermark.
func FusePlan(
	watermark uint32,
	qSize int,
	sepSeq uint32,
	propTight int64,
	targetVer uint32,
	rollbackVer uint32,
	offsets map[string]int64,
	bySeq map[uint32][]frame.Row,
	allRows map[uint32][]frame.Row,
) Outcome {
	var spreadMin, spreadMax int64
	for _, off := range offsets {
		if spreadMin == 0 && spreadMax == 0 {
			spreadMin, spreadMax = off, off
			continue
		}
		if off < spreadMin {
			spreadMin = off
		}
		if off > spreadMax {
			spreadMax = off
		}
	}
	band := "tight"
	if spreadMax-spreadMin > propTight {
		band = "wide"
	}

	accepted := map[uint32]uint32{}
	repair := uint32(0)
	loss := uint32(0)
	live := map[string]struct{}{}
	rollbackClean := true
	regionKeep := map[string]bool{}

	seqs := make([]uint32, 0, len(bySeq))
	for s := range bySeq {
		seqs = append(seqs, s)
	}
	for _, s := range op_rUint(seqs) {
		rows := bySeq[s]
		buckets := map[[2]string][]frame.Row{}
		for _, row := range rows {
			key := [2]string{itoaU(row.Ver), row.Region}
			buckets[key] = append(buckets[key], row)
		}
		var pickedKey [2]string
		var pickedRows []frame.Row
		var bestAdj int64
		found := false
		for key, items := range buckets {
			memSet := map[string]struct{}{}
			for _, it := range items {
				memSet[it.ServiceID] = struct{}{}
			}
			if !quorumgate.OpQ(len(memSet), qSize) {
				continue
			}
			valid := make([]frame.Row, 0, len(items))
			for _, it := range items {
				if vercheck.OpValid(it.RolloutSeq, it.ServiceID, it.Ver, it.CRC) {
					valid = append(valid, it)
				}
			}
			if len(valid) < qSize {
				continue
			}
			adj := skew.AdjustWall(valid[0], offsets[valid[0].Region])
			for _, it := range valid[1:] {
				a := skew.AdjustWall(it, offsets[it.Region])
				if a < adj {
					adj = a
				}
			}
			if !found || adj < bestAdj {
				found = true
				bestAdj = adj
				pickedKey = key
				pickedRows = valid
			}
		}
		if !found {
			loss++
			continue
		}
		for _, it := range buckets[pickedKey] {
			if !vercheck.OpValid(it.RolloutSeq, it.ServiceID, it.Ver, it.CRC) {
				repair++
			}
		}
		ver := parseU(pickedKey[0])
		if ver > sepSeq {
			mem := map[string]struct{}{}
			for _, it := range pickedRows {
				mem[it.ServiceID] = struct{}{}
			}
			if len(mem) < qSize {
				rollbackClean = false
			}
		}
		rid := pickedKey[1]
		if ver >= targetVer {
			regionKeep[rid] = true
		}
		for _, it := range pickedRows {
			live[it.Region] = struct{}{}
		}
		accepted[s] = ver
	}

	global := uint32(0)
	for s := uint32(1); ; s++ {
		if s <= watermark {
			global = s
			continue
		}
		if _, ok := accepted[s]; ok {
			global = s
			continue
		}
		break
	}

	adopted := uint32(0)
	for s, ver := range accepted {
		if s <= global && ver > adopted {
			adopted = ver
		}
	}
	for _, rows := range allRows {
		for _, row := range rows {
			if row.RolloutSeq > global {
				continue
			}
			if ver, ok := accepted[row.RolloutSeq]; ok {
				if row.Ver == ver && vercheck.OpValid(row.RolloutSeq, row.ServiceID, row.Ver, row.CRC) && row.Ver > adopted {
					adopted = row.Ver
				}
			} else if row.RolloutSeq <= watermark && row.Ver > adopted {
				adopted = row.Ver
			}
		}
	}

	revert := uint32(0)
	keep := uint32(0)
	for rid := range offsets {
		if regionKeep[rid] {
			keep++
		} else {
			revert++
		}
	}

	return Outcome{
		AdoptedVer:        adopted,
		ConvergeSeq:       global,
		StaleCacheRepairs: repair,
		PropagationGaps:   loss,
		ServicesUp:        uint32(len(live)),
		RevertCount:       revert,
		KeepCount:         keep,
		PropBand:          band,
		RollbackClean:     rollbackClean,
	}
}

func op_rUint(seqs []uint32) []uint32 {
	out := append([]uint32(nil), seqs...)
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j] < out[i] {
				out[i], out[j] = out[j], out[i]
			}
		}
	}
	return out
}

func itoaU(v uint32) string {
	if v == 0 {
		return "0"
	}
	var buf [12]byte
	i := len(buf)
	n := v
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

func parseU(s string) uint32 {
	var n uint32
	for _, c := range s {
		if c < '0' || c > '9' {
			continue
		}
		n = n*10 + uint32(c-'0')
	}
	return n
}
""",
        "internal/driver/run.go": """package driver

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"lab.local/flag_rollout_recovery/internal/config"
	"lab.local/flag_rollout_recovery/internal/engine"
)

// Report is the outward JSON document.
type Report struct {
	SchemaVersion       string `json:"schema_version"`
	PlanID              string `json:"plan_id"`
	AdoptedVer          uint32 `json:"adopted_ver"`
	ConvergeSeq         uint32 `json:"converge_seq"`
	StaleCacheRepairs   uint32 `json:"stale_cache_repairs"`
	PropagationGaps     uint32 `json:"propagation_gaps"`
	ServicesUp          uint32 `json:"services_up"`
	RevertCount         uint32 `json:"revert_count"`
	KeepCount           uint32 `json:"keep_count"`
	PropBand            string `json:"prop_band"`
	RollbackClean       bool   `json:"rollback_clean"`
	DigestHex           string `json:"digest_hex"`
}

// RunActive loads the active plan and returns a filled report.
func RunActive(appRoot string) (Report, error) {
	dir, err := config.ActivePaths(appRoot)
	if err != nil {
		return Report{}, err
	}
	plan, profiles, rows, offsets, err := config.LoadPlan(dir)
	if err != nil {
		return Report{}, err
	}
	out := engine.Replay(plan.PlanID, plan.QSize, plan.SepSeq, plan.PropTightMS, plan.TargetVer, plan.RollbackVer, profiles, rows, offsets)
	ck := "true"
	if !out.RollbackClean {
		ck = "false"
	}
	digest := sha256.Sum256([]byte(fmt.Sprintf(
		"%s|%d|%d|%d|%d|%d|%d|%d|%s|%s",
		plan.PlanID,
		out.AdoptedVer,
		out.ConvergeSeq,
		out.StaleCacheRepairs,
		out.PropagationGaps,
		out.ServicesUp,
		out.RevertCount,
		out.KeepCount,
		out.PropBand,
		ck,
	)))
	return Report{
		SchemaVersion:     "1",
		PlanID:            plan.PlanID,
		AdoptedVer:        out.AdoptedVer,
		ConvergeSeq:       out.ConvergeSeq,
		StaleCacheRepairs: out.StaleCacheRepairs,
		PropagationGaps:   out.PropagationGaps,
		ServicesUp:        out.ServicesUp,
		RevertCount:       out.RevertCount,
		KeepCount:         out.KeepCount,
		PropBand:          out.PropBand,
		RollbackClean:     out.RollbackClean,
		DigestHex:         hex.EncodeToString(digest[:]),
	}, nil
}
""",
        "internal/driver/emit.go": """package driver

import (
	"encoding/json"
	"os"
)

// EmitReport writes the recovery report JSON.
func EmitReport(path string, rep Report) error {
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}
""",
        "internal/observability/stub.go": """package observability

// Stub holds noop metrics hooks for the recovery driver.
func Stub() {}
""",
        "internal/merge/op_r_test.go": """package merge

import "testing"

func TestFusePlanEmpty(t *testing.T) {
	out := FusePlan(0, 3, 5, 25, 2, 1, map[string]int64{}, map[uint32][]frame.Row{}, map[uint32][]frame.Row{})
	if out.ConvergeSeq != 0 {
		t.Fatalf("unexpected converge %d", out.ConvergeSeq)
	}
}
""",
        "tools/digest_cli/main.go": """package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
)

func main() {
	if len(os.Args) != 11 {
		fmt.Fprintln(os.Stderr, "usage: digest_cli plan adopted converge repair gaps up revert keep band clean")
		os.Exit(2)
	}
	plan := os.Args[1]
	adopted, _ := strconv.ParseUint(os.Args[2], 10, 32)
	converge, _ := strconv.ParseUint(os.Args[3], 10, 32)
	repair, _ := strconv.ParseUint(os.Args[4], 10, 32)
	gaps, _ := strconv.ParseUint(os.Args[5], 10, 32)
	up, _ := strconv.ParseUint(os.Args[6], 10, 32)
	revert, _ := strconv.ParseUint(os.Args[7], 10, 32)
	keep, _ := strconv.ParseUint(os.Args[8], 10, 32)
	band := os.Args[9]
	clean := os.Args[10]
	payload := fmt.Sprintf("%s|%d|%d|%d|%d|%d|%d|%d|%s|%s", plan, adopted, converge, repair, gaps, up, revert, keep, band, clean)
	sum := sha256.Sum256([]byte(payload))
	fmt.Println(hex.EncodeToString(sum[:]))
}
""",
    }

    for rel, body in go_files.items():
        w(TASK / "environment" / rel, body)

    # fix merge test import
    merge_test = TASK / "environment" / "internal" / "merge" / "op_r_test.go"
    merge_test.write_text(
        merge_test.read_text().replace(
            "map[uint32][]frame.Row{}", "map[uint32][]frame.Row{}"
        )
    )
    merge_test.write_text(
        """package merge

import (
	"testing"

	"lab.local/flag_rollout_recovery/pkg/frame"
)

func TestFusePlanEmpty(t *testing.T) {
	out := FusePlan(0, 3, 5, 25, 2, 1, map[string]int64{}, map[uint32][]frame.Row{}, map[uint32][]frame.Row{})
	if out.ConvergeSeq != 0 {
		t.Fatalf("unexpected converge %d", out.ConvergeSeq)
	}
}
"""
    )

    # rust cachegate
    w(
        TASK / "environment" / "cachegate" / "Cargo.toml",
        """[package]
name = "cachegate"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["staticlib"]
""",
    )
    w(
        TASK / "environment" / "cachegate" / "src" / "lib.rs",
        """/// CgApplyLag folds a propagation lag band into a regional clock skew baseline (milliseconds).
#[no_mangle]
pub extern "C" fn cg_apply_lag(base_ms: i64, lag_ms: i64) -> i64 {
    if lag_ms == 0 {
        return base_ms;
    }
    base_ms + lag_ms
}
""",
    )
    w(
        TASK / "environment" / "cachegate" / "lag_fold.h",
        """#ifndef LAG_FOLD_H
#define LAG_FOLD_H
#include <stdint.h>
int64_t cg_apply_lag(int64_t base_ms, int64_t lag_ms);
#endif
""",
    )
    w(
        TASK / "environment" / "cachegate" / "bridge.go",
        """package cachegate

/*
#cgo LDFLAGS: ${SRCDIR}/target/release/libcachegate.a -ldl -lm
#include "lag_fold.h"
*/
import "C"

// ApplyLag combines regional clock skew with an optional propagation lag band.
func ApplyLag(baseMS int64, lagMS int64) int64 {
	return int64(C.cg_apply_lag(C.longlong(baseMS), C.longlong(lagMS)))
}
""",
    )

    # build cargo lock via cargo
    w(
        TASK / "environment" / "scripts" / "build.sh",
        """#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"
export CGO_ENABLED=1

mkdir -p /app/bin
cd /app/cachegate
cargo build --release --locked 2>/dev/null || cargo build --release
cd /app
GOFLAGS=-mod=mod go build -trimpath -buildvcs=false -o /app/bin/flag_recover ./cmd/flag_recover
""",
    )

    w(
        TASK / "environment" / "ci" / "smoke.sh",
        """#!/bin/bash
set -euo pipefail
bash /app/scripts/build.sh
""",
    )

    w(
        TASK / "environment" / "docs" / "mesh_topology.md",
        """# Regional mesh topology

Fifty logical services are grouped into five regional shards (ten services per shard).
Each shard contributes rollout observations and a stale-mark watermark used during replay.
""",
    )

    w(
        TASK / "environment" / "ops" / "retention_note.txt",
        """Rollout history segments are retained for seven days in the offline lab mirror.
""",
    )

    w(
        TASK / "environment" / "profiles" / "default.json",
        """{"driver": "flag_recover", "fixture_gate": "TB_FLAG_FIXTURE"}
""",
    )

    w(
        TASK / "environment" / "schemas" / "report.example.json",
        """{
  "schema_version": "1",
  "plan_id": "alpha",
  "adopted_ver": 5,
  "converge_seq": 6,
  "stale_cache_repairs": 0,
  "propagation_gaps": 0,
  "services_up": 5,
  "revert_count": 2,
  "keep_count": 3,
  "prop_band": "tight",
  "rollback_clean": true,
  "digest_hex": "0000000000000000000000000000000000000000000000000000000000000000"
}
""",
    )

    w(
        TASK / "environment" / "harness" / "notes.txt",
        """Offline harness uses TB_FLAG_FIXTURE gate for deterministic replay packs.
""",
    )

    w(
        TASK / "environment" / "data" / "catalog_note.txt",
        """Active mesh plans live under data/active; regression packs ship with the verifier fixtures.
""",
    )

    w(
        TASK / "environment" / "README.md",
        """# Flag rollout recovery lab

Mixed-language recovery driver for regional shard convergence after a partial control-plane push.
""",
    )

    w(
        TASK / "environment" / "verifier-requirements.txt",
        """pytest==8.4.1
pytest-json-ctrf==0.3.5
""",
    )

    w(
        TASK / "environment" / ".dockerignore",
        """target
**/target
""",
    )

    # Dockerfile
    w(
        TASK / "environment" / "Dockerfile",
        open(SWARM / "environment" / "Dockerfile").read()
        .replace("swarm-mesh-coord-heal", "flag-rollout-recovery")
        .replace("swarm_heal", "flag_recover")
        .replace("radiogate", "cachegate")
        .replace("radio_fold.h", "lag_fold.h")
        .replace("COPY harness /app/harness\n", "")
        .replace(
            "COPY profiles /app/profiles\n",
            "COPY profiles /app/profiles\nCOPY harness /app/harness\n",
        ),
    )

    # fixtures from swarm
    for src, dst in [
        ("swarm_alpha", "mesh_alpha"),
        ("swarm_beta", "mesh_beta"),
        ("swarm_gamma", "mesh_gamma"),
        ("swarm_delta", "mesh_delta"),
        ("swarm_epsilon", "mesh_epsilon"),
    ]:
        convert_swarm_fixture(src, dst)

    # active = alpha
    active = TASK / "environment" / "data" / "active"
    if active.exists():
        shutil.rmtree(active)
    shutil.copytree(TASK / "tests" / "fixtures" / "mesh_alpha", active)

    # tests
    shutil.copy(SWARM / "tests" / "test.sh", TASK / "tests" / "test.sh")

    print("generated", TASK)


if __name__ == "__main__":
    main()
