# Workflow Prompts

All prompts for the Terminal-Bench 3 task creation pipeline, in order.

## Overview

```
Step 1:           ChatGPT  → Find the idea (creative, iterative)
Step 2a:          Cursor   → Validate idea + produce authoring spec + reviewer appendix (automated loop)
                             [you review specs/<task-name>.md and specs/<task-name>-reviewer.md]
                             [agent runs `validate_loop.py finalize <task>` as the strict v2 gate]
Step 2b:          Cursor   → Draft files + mechanical gates + ORACLE 1X SANITY
                               1. Create task files
                               2. Discovery budget + discoverability gate (paper — free)
                               3. run_static_checks.py (ms)
                               4. collapse_check.py (seconds)  ← mechanical, runs BEFORE any oracle
                               5. oracle 1x + NOP (minutes, parallel) — sanity check only
                             Any check that fires forces re-entry at the cheapest unchecked point,
                             so expensive oracle time is never wasted on a collapse-failing task.
                             Do NOT run oracle 10x here — that's Step 4's job.
Step 3a (opt-in): Cursor   → Diagnostics for REVISIONS only — GPT-5.2 quality check (3a-Q)
                             and/or verifier_health.py (3a-V). Completely optional for new tasks.
Step 3b:          Cursor   → LLM-LEVEL REVIEW ONLY (paper, no oracle runs). Three sub-steps:
                               1. Structural review against @review-and-submit.mdc
                               2. LLM-level collapse audit (@difficulty-calibration.mdc Part A)
                               3. Per-test feasibility paper review (Part B; escalate to 3a-V if needed)
                             Mechanical collapse_check already ran in Step 2b — not repeated here.
                             Any edit dirty-flags back to Step 2b's static → collapse → 1x oracle +
                             NOP (NOT 10x — 10x is deferred to Step 4).
Step 3b→4 (re-entry):  Cursor   → DIRTY-FLAG RE-VALIDATION (only when you edited a task file in Step 3a/3b)
                              If you made ANY task-file edit during Step 3a or Step 3b, the Step 2b
                              mechanical evidence is stale. Before proceeding to Step 4, rerun the
                              Step 2b mechanical chain for the current working tree state:

                                python3 run_static_checks.py --task-dir tasks/<task-name> --version edition_2
                                python3 collapse_check.py tasks/<task-name>
                                harbor run -p "tasks/<task-name>" -a oracle
                                harbor run -p "tasks/<task-name>" -a nop

                              Then rerun Step 3b (paper review) to confirm no concept-level regressions.
                              Only after that is it valid to run Step 4's 10x oracle stress test.
Step 4:           Cursor   → ORACLE 10X + Package + Approval Gate. Five sub-steps:
                               1. Oracle 10x flakiness check (the ONLY place 10x runs)
                               2. Generate zip (excluding FORBIDDEN_ROOT_FILES like output_contract.toml)
                               3. approve_task.py (static + collapse + zip validation re-run)
                               4. Mirror task.toml + instruction.md into repo_tests/fixtures/tasks/<name>/
                               5. Decision: ACCEPT / ACCEPT WITH NOTES / REJECT. No SEND FEEDBACK.
Platform submit:           → Upload the zip produced by Step 4.
```

### Construction-to-spec, not construction-then-validate (the primary principle)

Every check in this workflow — `run_static_checks.py`, `collapse_check.py` RC1-RC7, `@review-and-submit.mdc` §1-7, `@difficulty-calibration.mdc` Part A and Part B — is fully documented upstream. The agent drafting in Step 2b has access to every rule before writing a single file. The expected outcome of a disciplined draft is **one-shot PASS through every check**. The checks exist to catch hallucination and drift, not to discover the correct design interactively.

This shapes the entire workflow:

- **Step 2b** is a construction phase, spec-aware throughout. The Construction discipline at the top of Step 2b names every rule an author must internalize before drafting. File-level construction hints point each file at the rules it must satisfy _at construction time_.
- **The mechanical checks in Step 2b** (`run_static_checks.py`, `collapse_check.py`, oracle 1x + NOP) are **verification, not discovery**. The first-try verdict on all three should be PASS. A FAIL means construction missed a rule that was already visible — fix the specific violation with a minimal edit, don't iterate to explore.
- **Step 3b** is a second-opinion verification pass. Its default outcome is also clean — the only findings that regularly survive disciplined construction are concept-level judgement calls the mechanical checks can't see.
- **Edits that do happen** use the preservation discipline below: they're labelled, minimal, and don't regress gates that have already passed.

If `run_static_checks.py`, `collapse_check.py`, or oracle + NOP regularly FAIL on first try, the fix is not "add more iterations" — the fix is "tighten construction discipline." The checks' job is hallucination-catching, not design coaching.

### The cheapest-first ordering (why it still matters)

Even in the disciplined default case, any edit that does happen should re-enter verification at the cheapest check that hasn't re-confirmed the new state. Checks that can force task-file edits run in cost order: paper checks, then `run_static_checks.py` (ms), then `collapse_check.py` (seconds), then oracle 1x + NOP (minutes), then LLM review (paper), then oracle 10x (many parallel minutes). Every edit bounces re-entry back to the cheapest unverified check, so no expensive run is ever invested in a task that a later cheap check would reject.

The 10x oracle stress test runs exactly **once per development cycle**, at the start of Step 4, after every structural and concept-level edit is already settled. Do not invoke `harbor run -p ... -a oracle -k 10 -n 10` from Step 2b or Step 3b. The cheap sanity variant is `harbor run -p ... -a oracle` (no -k = one trial).

### Preservation discipline (why re-runs should confirm, not discover)

Construction-to-spec gets the task right on first draft. Cheapest-first ordering prevents wasted work when an edit does happen. Preservation discipline makes those edits minimal: every gate that passes is an invariant on all later work — a later edit should be designed to preserve every already-passing gate. The dirty-flag rule is the safety net that catches regressions; preservation discipline is the default plan that makes those regressions rare. When a Step 3b (or Step 3a, or Step 4) fix breaks an earlier gate, it should be a labelled _justified regression_, not the normal consequence of any fix. See Step 3b's "Preservation discipline" subsection for the edit-risk map and textual self-checks; the same discipline applies to Step 3a and Step 4 fix loops.

### Ralph discipline within the Step model

The TB3 step model already implements the Ralph loop pattern; this
section names the Ralph discipline so the mapping is explicit. There
is no parallel Loop A/B/C/D/E vocabulary — Steps 1, 2a, 2b, 3b, and 4
are the loops, and the existing harness (`validate_loop.py`,
`approve_task.py`, `specs/`, `repo_tests/`) is the machinery.

- **Step 2a (idea validation)**: one task spec per loop. Validate against
  `idea-validation.mdc`; produce `specs/<task-name>.md` with all required
  sections (Authoring Brief, Triviality Ledger, Per-gate Pitfall Inventory,
  Initial Draft Commitments). `validate_loop.py` is the gate; `lint_spec.py`
  enforces the v2 mandatory sub-sections.

- **Step 2b (construction)**: one validated spec per loop. Draft files,
  then run `./scripts/check-task.sh tasks/<task-name>` (Phase A static +
  collapse, Phase B packaging preview, Phase C `.step2b-checksum`), then
  `harbor run -p tasks/<task-name> -a oracle` (1x), then `harbor run -p
tasks/<task-name> -a nop`. Failure → return to drafting; the
  `.step2b-checksum` will catch any subsequent edits and force a
  preflight re-run before approval.

- **Step 3b (review)**: one constructed task per loop. Paper review
  against `review-and-submit.mdc` and `difficulty-calibration.mdc`. Any
  edit returns to Step 2b; the dirty-flag is mechanical (the sentinel
  becomes stale and `approve_task.py` refuses).

- **Step 4 (packaging)**: clean Step 2b + 3b evidence. Oracle 10x, build
  the shipping zip, run `approve_task.py` (which verifies the
  `.step2b-checksum` before doing anything else).

- **Cross-cutting (failure triage)**: when a gate fails three times the
  same way, file a `CNI.md` entry citing the three instances. Choose the
  cheapest enforcement that prevents recurrence (script → static check →
  collapse check → scoped rule → deep rule → critical rule). This is the
  Ralph "convert failures into rules" discipline; the trigger threshold
  and implementation order are documented in `CNI.md` § "Promotion and
  demotion policy".

### Setup

- **Step 1**: Attach the entire `web/` folder to ChatGPT (drag and drop all 6 files).
- **Steps 2a–4**: Open the repo in Cursor. The `.cursor/rules/` files auto-apply.

---

## Step 1: ChatGPT — Build the Step-2a Seed Bank

Use **exactly two prompts** for the default Step 1 flow.

The default Step 1 output is **not** a tiny shortlist. It is a **goal-sized Step-2a-ready seed bank** you can take into Cursor. Unless you specify otherwise, the default target is **150 Step-2a-ready seeds** after Option A.

### Prompt 1 — Option B: build the seed bank

Attach the entire `web/` folder and say:

```text
Run Option B from `web/bulk-idea-generation.md` in goal-sized opus-weak mode.
The final target after Option A is 150 Step-2a-ready seeds.
Use the four Opus-weak categories, keep the bank category-balanced, keep Topology distinct within category, and return one downloadable `.md` seed-bank file.
```

### Prompt 2 — Option A: consolidate the final bank

Attach the `.md` file produced by Prompt 1 and say:

```text
Run Option A from `web/option-a-seed-refinement.md` in step2a-bank mode against the attached bulk-ideas file.
The final target is 150 Step-2a-ready seeds.
Repair or replace weak seeds instead of collapsing to a tiny shortlist.
Keep the four Opus-weak categories balanced, keep Topology distinct within category, and return one downloadable `.md` file.
```

### Optional strict reduction pass

Only if you later want a tiny shortlist for immediate drafting, run Option A again in `finalist mode`.

### Practical notes

- The Step 1 output should be a **bank you can mine inside Cursor**, not a celebration that only 4 or 8 ideas survived.
- If one category saturates, narrow to better subsystem framings before backfilling from another category.
- Keep Step 1 ideas in hard-only territory: no blank-canvas implementations, no obvious mediums, no fake hardness from giant scope or busywork.
- Option A is allowed to **refine or replace** weak seeds to keep the final bank full. That is the intended behavior.

Once you have the Step-2a-ready bank file, move to Step 2a in Cursor and validate whichever seed you want to pursue first.

---

## Step 2a: Cursor — Validate Idea & Produce Specs

One prompt. Cursor runs a validation loop automatically using `validate_loop.py` as the decision oracle. No manual pasting between attempts.

```text
Validate this task idea and produce an authoring spec plus a separate reviewer appendix. Do NOT create any task files under tasks/.

You will run an automated validation loop. The script validate_loop.py manages the loop state and tells you what to do at each step.

Follow @idea-validation.mdc for all checks, rubric axes, and spec format.
Follow @difficulty-calibration.mdc Part A for the collapse audit.
Use `specs/validation_schema.json` as the required evidence contract for each attempt.

## Step 0: Initialize

Run:
  python validate_loop.py init <task-name>

Read the ACTION line from the output.

## Loop: repeat until ACTION is GO or STOP

### On ACTION: CONTINUE

1. Evaluate the 5 hardness axes from @idea-validation.mdc (Discover, Synthesize, Diagnose, Navigate coupling, Reason beyond training). For EACH axis, write 1-2 sentences explaining how this task satisfies it. If any axis fails, the task cannot be hard — this is a FAIL.
2. Run the instruction completeness test: "Can the agent solve this by reading ONLY instruction.md without deeply engaging with the codebase?" If yes, this is a FAIL.
3. Run all 20 anti-trivialization checks from @idea-validation.mdc. For EACH check, write 1-2 sentences of reasoning BEFORE the Pass/Warn/Fail verdict.
4. Evaluate against the 6 rubric axes. For EACH axis, write 1 sentence of reasoning and a Pass/Warn/Fail verdict. Show all 6 explicitly — do not summarize as "all pass."
5. Run the collapse audit from @difficulty-calibration.mdc Part A (full template).
6. If this is attempt 2+: for each check that was WARN or FAIL in a previous attempt and is now PASS, explicitly state what design change caused the improvement. Do not just rephrase the reasoning — name the structural change.
7. If you changed anything from the original idea beyond fixing the flagged issues (language, scope, domain, architecture, number of modules, etc.), state each change and why it was necessary.
8. Naming pass and token-provenance audit (run BEFORE building the
   evidence JSON):
   a. Draft the symptoms-only instruction prose. Extract every
      noun from it. That extracted list is BOTH
      `naming_pass.instruction_nouns_extracted` and
      `construction_manifest.code_forbidden_tokens` — populate
      both from the same source list, do not derive separately.
   b. For every entry in `construction_manifest.symbol_table`
      (kind, signature, path, symbol name), every path in
      `flipping_point_contract.locations`, every entry in
      `decoy_manifest`, and every test function name you plan:
      check whether any token from the noun list appears as a
      case-insensitive substring. If yes, rename it. Record each
      rename as `{original, renamed_to, reason}` in
      `naming_pass.renames_during_drafting`. If no renames were
      needed, leave the list empty — the loop will WARN but
      accept; do not fabricate renames to suppress the warning.
   c. Compute concentration math. Total tests = size of the union
      of `controls_tests` across all
      `flipping_point_contract.locations`. For each location:
      test_count = len(controls_tests), ratio = test_count /
      total_tests. Populate `naming_pass.concentration_math`
      accordingly. The validator will recompute and reject on
      mismatch — your numbers must be honest, not aspirational.
   d. Verify every entry in `decoy_manifest` has a non-empty
      `rhymes_with` field naming a fix-path symbol. The schema
      now requires this; missing rhymes will fail schema
      validation at record time.
9. Build a structured evidence JSON that matches `specs/validation_schema.json`. Populate ALL required fields. In particular:
   - `hardness_axes`
   - `anti_trivialization_checks` (21 entries — includes `topology_distribution_test`)
   - `discovery_budget`
   - `instruction_specificity`
   - `attack_path`
   - `smallest_plausible_patch`
   - `topology_enumeration` (BLOCKING): at least 3 distinct fix topologies, each naming ≥3 code locations that must coordinate, and for each a one-sentence explanation of why no single location is sufficient. If you cannot articulate 3 such topologies, the idea has a one-function-exploit locus — reject.
   - `construction_manifest` (BLOCKING): the machine-checkable handoff to Step 2b. Must include `symbol_table` (opaque pre-assigned names for every fix-path symbol, ≥3 entries), `flipping_point_contract` (≥3 locations across distinct roots, with per-location test subsets summing under a 50% concentration cap), `decoy_manifest` (≥2 rhyming helper modules), and `code_forbidden_tokens` (every domain noun extracted from instruction.md — these are banned from CODE symbol names on the fix path, NOT from the instruction itself; `instruction.md` uses whatever standard domain language makes the contract clear).
   - `naming_pass` (BLOCKING): the audit trail from step 8. Carries `instruction_nouns_extracted` (the same list used to populate `code_forbidden_tokens`), `renames_during_drafting` (each `{original, renamed_to, reason}` rename you applied; empty list is allowed but warns), `test_names_audited` (≥3 final test function names), and `concentration_math` (total_tests + per-location test_count and ratio matching the validator's recomputation).
   The `discovery_budget` field is BLOCKING: include at least 3 non-trivial solver discoveries the finished task should force from the codebase/runtime. For each item, name the discovery, where it should live after Step 2b, and why instruction.md must not reveal it. If you cannot list 3, the idea is easy.
   The `instruction_specificity` field is BLOCKING: for a hard candidate, `level` must be `symptoms-only`. If the best honest level is `spec-complete` or `cause-revealing`, the idea cannot GO.
10. Count your FAILs and WARNs from the evidence and written review. Do not let the score contradict the structured verdicts.
11. Produce two documents using the format in @idea-validation.mdc:
    - an authoring spec for Step 2b
    - a separate reviewer appendix for human review only
    The Decision line in BOTH files must include the attempt number (e.g., "GO — Attempt 2. ...").
    Hold both docs in your context — do NOT save them yet.
12. Save the structured evidence JSON to a temporary path, for example:
      /tmp/<task-name>-validation-evidence.json
13. Record the result FIRST (this determines where to save and whether the evidence is sufficient):
      python validate_loop.py record <task-name> --evidence /tmp/<task-name>-validation-evidence.json
14. Read `SAVE_TO` and `REVIEWER_SAVE_TO` from the script's output. NOW save the authoring spec to `SAVE_TO` and the reviewer appendix to `REVIEWER_SAVE_TO`.
    Each file must contain ONLY this variant's content — no comparison tables, no previous attempt data, no clutter.
    If `SAVE_TO` is `DISCARD`, do not save either file — the attempt was a regression and should not be persisted.
    IMPORTANT: always save AFTER record, never before. The script decides whether this attempt should overwrite the best specs or go to paired candidate files.
15. After saving both files on a GO action, run the strict lint gate:
      python validate_loop.py finalize <task-name>
    If it exits 0, proceed to step 16.
    If it exits 1, the saved spec violates the v2 contract — read
    the failure list, amend the saved files in place to add
    `version: 2` and the three required subsections (or fix the
    specific failures the gate names), then re-run finalize. Do
    NOT re-run `record` — the evidence is unchanged; only the spec
    text needed correction.
16. Read the script's ACTION. It will say one of:
    - ACTION: CONTINUE — list your current WARNs and FAILs. For each, propose a specific concrete change (not vague — e.g., "move matvec accounting into a separate module with its own seeded defect" not "spread bugs around"). Apply ALL changes to create a new variant. Go back to step 1 of this loop with the new variant.
    - ACTION: SELECT — go to the SELECT section below.
    - ACTION: GO — go to the DONE section below.
    - ACTION: STOP — go to the DONE section below.

### On ACTION: SELECT

The script hit a plateau — multiple variants have the same score but may differ in quality.
1. Read the CANDIDATES line from the script output. Each entry is `attempt=authoring-spec|reviewer-appendix`, so you can compare the attempt number and both file paths directly.
2. Read each candidate authoring spec and reviewer appendix.
3. For each, run the collapse audit and summarize: collapse verdict, oracle complexity (lines), editable frontier (files), residual hardness (one sentence).
4. Pick the winner — the spec a reviewer would most confidently approve.
5. Tell the script (it handles promotion and cleanup automatically):
     python validate_loop.py select <task-name> --winner <attempt-number-or-listed-path>
   Examples:
   - `python validate_loop.py select <task-name> --winner 3`
   - `python validate_loop.py select <task-name> --winner specs/<task-name>-candidate-1.md`
   - `python validate_loop.py select <task-name> --winner specs/<task-name>-candidate-1-reviewer.md`

### On ACTION: GO or STOP — DONE

Report:
- Final decision: GO or STOP
- Winning attempt number (if GO)
- Stopping reason (perfect / plateau+selection / max attempts / unfixable)
- Final FAIL/WARN counts
- The authoring spec path (if GO): specs/<task-name>.md
- The reviewer appendix path (if GO): specs/<task-name>-reviewer.md

If STOP: explain why the idea family cannot be saved.

Here is the task idea:

[PASTE THE WINNING IDEA FROM STEP 1]
```

**After this runs:** Open `specs/<task-name>.md` and `specs/<task-name>-reviewer.md`. Review both. If satisfied, move to Step 2b. Drafting should consume only the authoring spec.

---

## Step 2b: Cursor — Create Task Files

Only run this after you've reviewed and approved the Step 2a authoring spec and reviewer appendix.

```text
Create a new task from the authoring spec file below.
Follow @task-creation.mdc for all file rules.

Read ONLY the authoring spec file while drafting the task. Do NOT open the reviewer appendix during drafting.

Use the authoring spec's metadata, public contract, failure topology, environment shape, required artifacts, and test plan to create all task files. The brief is intentionally non-exhaustive: you must design the exact internal file tree and implementation scaffolding yourself while preserving the brief's public contract and difficulty profile.

Place files under tasks/<task-name>/ (get the task name from the authoring spec's Metadata section).

## Construction discipline (read BEFORE drafting any file)

Every check that runs after File creation — `run_static_checks.py`, `collapse_check.py` RC1-RC7, oracle 1x, NOP, Step 3b's structural review, Part A collapse audit, Part B feasibility — has its rules fully documented upstream. You already know what every check will examine. The expected outcome of disciplined construction is **one-shot PASS through every mechanical and LLM-level check**. The checks are hallucination catchers, not design oracles — a FAIL after construction means the draft missed a rule you already had access to, not that the correct design is being discovered interactively.

Before drafting any file, internalize these rule sources:

- `@task-creation.mdc` — file layout, canonical `test.sh` template (standard vs. UI), Dockerfile rules, `output_contract.toml` contract, humanization rules for `instruction.md`, milestone naming.
- `@review-and-submit.mdc` §1-7 — the structural checklist Step 3b will walk (Instruction, Environment, Oracle Solution, Verifiers, Task Metadata, Task Structure, Difficulty Calibration). Every bullet there is something you can satisfy at construction.
- `@difficulty-calibration.mdc` Part A — the collapse audit template (smallest plausible patch, editable frontier, requirement-to-file map, oracle LOC, discoverability, red flags, residual hardness). Design the task so this audit returns PASS on the first read.
- `@difficulty-calibration.mdc` Part B — per-test feasibility risks: single-valid-approach, chain-dependency, order-sensitivity, flakiness, niche-technique. Avoid creating any of these while writing tests.
- `collapse_check.py` RC1-RC7 + RC8 + CR1-CR7 — mechanical collapse and fix-surface rules. Each translates to a specific construction constraint:

| Rule | Axis                         | What this means at construction time                                                                                                                                  |
|------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| RC1  | Oracle simplification        | `solve.sh` must add logic, not just delete/revert. If the "fix" is `sed -i '/BUG/d'`, the task is trivial — redesign.                                                  |
| RC2  | Oracle predictability        | File, directory, and test names must not encode the task contract. No `broken_*`, `buggy_*`, `fix_me_*`, `golden_*` tokens in solver-visible surfaces.                 |
| RC3  | Verifier shallowness         | Tests must assert domain-correct computed values, not format/schema/existence alone. Every explicit prohibition in `instruction.md` needs a direct test.               |
| RC4  | Tamper surface               | Tests must not depend on files the agent can rewrite to bypass domain reasoning. Compute expected values in test code; don't read "golden" files from `environment/`.  |
| RC5  | Reference artifacts          | No answer-shaped golden/reference/broken fixtures on solver-visible surfaces (`instruction.md`, `tests/`, `environment/`). Embed expected values in test code.         |
| RC6  | Instruction specificity      | `instruction.md` stays symptoms-only. No algorithm names, schema enumerations, CLI flag lists, numeric thresholds, file/function locations, cause statements, recipes. |
| RC7  | Oracle triviality            | `solve.sh` non-boilerplate LOC ≥ 30 (≥ 80 is comfortable). If the genuine fix is <30 LOC, the task is too simple — redesign before drafting, don't pad.               |
| RC8  | Frontier concentration       | Oracle targets should not all cluster in one subsystem with small target files. Diagnostic WARN (no FAIL); paired with CR2 for the real gate.                          |
| CR1  | Symbol-table compliance      | Every oracle-touched symbol must match the authoring spec's `construction_manifest.symbol_table`. No invented domain-telegraphing names on the fix path.              |
| CR2  | Flipping-point contract      | Authoring spec's `flipping_point_contract` must name ≥3 locations across distinct roots with ≤50% test-control concentration. Static verification of the contract shape. |
| CR7  | Grep-resistance              | No instruction noun may appear as a function/class/path token on the fix path. Diagnostic WARN; pair with CR1 symbol-table compliance for the enforcement.             |

Construction is spec-aware, not spec-discovering. While writing each file, pre-validate against the rules relevant to that file. The mechanical checks afterward should confirm, not discover, that construction was correct. If you find yourself thinking "I'll let the check tell me," stop — read the rule now, apply it now.

## File creation

Create the files required by the brief and by `@task-creation.mdc`. The exact file set depends on task type. For each file below, the parenthetical names the primary rules you must satisfy *during construction*, not after.

**Standard tasks (most tasks):**
- `tests/test_outputs.py` — implement test plan, target 6+ tests. (RC3 domain correctness, RC4 tamper resistance, Part B feasibility risks, @review-and-submit.mdc §4 Verifiers, instruction_test_vocabulary static check.)
- `tests/test.sh` — start from the standard platform template in `@task-creation.mdc` and preserve its command order / control flow verbatim; only the documented semantic variations are allowed. (§4 template compliance, `shell_script_integrity` LF line endings.)

**Milestone tasks (number_of_milestones > 0):**
- All per-milestone content lives under `steps/milestone_N/`, NOT at the task root. The canonical layout for each milestone is `steps/milestone_N/{instruction.md, tests/{test.sh, test_mN.py}, solution/{solve.sh, solveN.sh}}`. Do not create a top-level `instruction.md`, `tests/`, `solution/`, `milestones.md`, or `milestone_X.md` for a milestone task. (See `task-creation.mdc` "Milestone task" for the full layout, naming, and `task.toml` shape.)
- `steps/milestone_N/tests/test_mN.py` — one test file per milestone, with assertions in a `TestMilestoneN` class, scoring only its own milestone. (@review-and-submit.mdc §4 milestone rules, RC3/RC4 as above.)
- `steps/milestone_N/tests/test.sh` — same template discipline as standard, one per milestone.
- `steps/milestone_N/solution/solveN.sh` — oracle for milestone N only, called by a tiny `steps/milestone_N/solution/solve.sh` wrapper.
- `task.toml` — `version = "2.0"`, `[metadata].number_of_milestones` equal to the number of `[[steps]]` blocks, each `[[steps]].name = "milestone_N"`, per-step `[steps.agent]` / `[steps.verifier]` timeouts, no top-level `[agent]` / `[verifier]`, no Harbor-only fields (`schema_version`, `[task]`, `min_reward`, `[steps.healthcheck]`, `[steps.verifier.env]`, `artifacts`, `multi_step_reward_strategy`, `workdir/setup.sh`).

**UI tasks (subcategories includes ui_building):** New UI building tasks are no longer accepted. In-progress instances may finish; do not start new ones. Below is the existing template for legacy/in-progress UI tasks only.
- `tests/test_outputs.py` — unit tests. (Same RC3/RC4/Part B as standard.)
- `tests/` e2e test files — Playwright/Vitest as specified in `@task-creation.mdc`. (§4 UI-task verifier rules.)
- `tests/test.sh` — copy the UI platform template from `@task-creation.mdc` (different from standard).

**All task types:**
- `instruction.md` — write human-style per humanization rules in `@task-creation.mdc`. (RC6 symptoms-only, §1 Instruction checklist, absolute paths, no emojis, no synthetic Deliverables/Artifacts/Acceptance-Criteria sections, no algorithm/CLI/schema/threshold/file-location leakage, no bold-markers on solution-adjacent values.)
- `task.toml` — fill in all metadata from the authoring spec. (§5 Task Metadata, `timeout_coherence`: `verifier.timeout_sec` ≥ `environment.build_timeout_sec` and ≤ 1800, `subcategories` not `task_subtypes`, 3-6 tags, matching `codebase_size` vs. env file count.)
- `output_contract.toml` — declare `user_visible_outputs`, `structured_outputs`, and `internal_harness_files`. The instruction must cover only the declared user-visible outputs and schemas; do not mention a literal `internal_harness_files` path in `instruction.md` unless that same path is also declared in `user_visible_outputs`. (Static `output_contract` check, `instruction` check for `internal_harness_files` leakage.)
- `environment/Dockerfile` — pin `FROM` by digest, pin apt versions, set a real `WORKDIR`, ensure every `COPY`/`ADD` source path resolves inside the build context. Do NOT copy `solution/`, `tests/`, or answer fixtures into the image. Test-only deps go in `tests/test.sh`, not here. (§2 Environment, `dockerfile_copy_sources` static check, `package_hygiene` static check.)
- `solution/solve.sh` — deterministic, no network, no randomness, no timing/wall-clock dependencies. Non-boilerplate LOC ≥ 30 (aim for 80+ for comfortable RC7). `set -euo pipefail` is allowed here (only). (RC1/RC7, §3 Oracle Solution.)
- All environment source files required by the authoring spec's environment shape and your chosen internal design. Do NOT embed golden hashes / reference outputs / expected digests in any file that solver-visible surfaces reach. Env file count must be ≥ 20 (anything less is `minimal` and blocked). (RC5, §2 env count, `package_hygiene`.)

When any constraint would force you off the authoring spec's design, stop and revise the draft rather than "work around" — the constraint is from a rule the spec already assumed you'd satisfy. This is the same discipline as Step 3b's preservation rule, applied at construction: every rule is an invariant, not a hurdle to clear retrospectively.

Check `@task-creation.mdc` for the correct template and file layout for your task type.

## Discovery budget confirmation (mandatory, run after all files exist)

Only after the task files exist, open the reviewer appendix. Use it ONLY for this confirmation step — not for initial drafting.

For each `Discovery budget` item in the reviewer appendix:
1. Confirm the discovery still exists in the built task and is still something the solver must recover from code/runtime behavior.
2. Confirm it lives in the planned location, or note the equivalent location you actually created.
3. Confirm instruction.md, file names, test names, comments, fixtures, and obvious runtime errors do NOT reveal it directly.

If any discovery disappeared, moved into an obvious single-file breadcrumb, or is now revealed by the solver-visible file surfaces or obvious runtime errors, revise the task and re-check the entire budget.

Report each discovery and how you confirmed it still survives.

## Discoverability gate (mandatory, run after all files exist)

Before finishing, use the solver-visible file-surface policy from `@task-creation.mdc`: the agent can inspect `instruction.md`, everything under `environment/`, everything under `tests/`, and the file/directory names within those surfaces. On the current repo policy, `task.toml` and `output_contract.toml` are authoring/package metadata and are NOT solver-visible for this gate.

Ask yourself — could the agent skip the hard reasoning and find the solution through surface-level signals in any of those file surfaces? If you run the broken task during review, also ask whether runtime error output leaks the fix.

1. Does the instruction point to specific code locations or implementation details instead of describing required behavior?
2. Do source/config/data files under `environment/` contain markers, flags, annotations, commented-out correct values, or structural hints that reveal fix locations or correct values?
3. Do file or directory names describe what's broken or what to fix?
4. Do test names or assertions reveal the solution steps rather than just what to verify?
5. If you ran the broken task, would runtime error output pinpoint the exact fix rather than just indicating something is wrong?

If ANY answer is yes: identify the signal and eliminate it. Then re-verify oracle still passes.

Report what you checked and what you changed (if anything).

## Static checks (verification, not discovery)

Run the task-scoped static checker:
  python3 run_static_checks.py --task-dir tasks/<task-name> --version edition_2

Then verify the environment file count (excluding Dockerfile/docker-compose):
  find tasks/<task-name>/environment -type f ! -iname 'Dockerfile' ! -iname 'docker-compose*' | wc -l

Must be 20 or more. If under 20, you skipped the env-file-count constraint in the Construction discipline — the authoring spec should have produced enough substantive environment files on the first draft. Do not add empty or trivial padding; if the task genuinely needs <20 files, the task is too small and should have been caught in Step 2a.

**Expected outcome:** PASS on the first run. Every rule `run_static_checks.py` enforces was visible to you during construction (task.toml schema, `test.sh` template conformance, timeout coherence, dockerfile COPY sources, package hygiene, shell script LF line endings, etc.). A FAIL means you missed a rule while drafting — read the specific failure, identify which construction-time rule it violates, apply the minimal fix that satisfies it without disturbing anything else. This is rare if construction followed the discipline.

## Mechanical collapse check (verification, not discovery)

Run:
  python3 collapse_check.py tasks/<task-name>

**Expected outcome:** PASS on the first run. Every signal `collapse_check.py` examines (RC1-RC7) was named in the Construction discipline. The expected verdict for a disciplined draft is PASS.

Interpret the result:
- **PASS (exit 0):** construction-to-spec succeeded. Proceed to the oracle + NOP sanity check below.
- **WARN (exit 2):** one or more RCs emitted non-fatal signals. Acceptable for a small number of WARNs with documented justification, but more than one WARN usually means construction drifted off the spec — reread the RC-to-construction mapping in the Construction discipline before continuing.
- **FAIL (exit 1):** construction missed an RC rule the task should have satisfied by design. Identify the violated RC from the failure output, map it back to the construction constraint it represents, and apply the smallest fix that satisfies it. **A FAIL here is a hallucination-catch, not a normal iteration cycle** — if FAILs recur, the issue is drafting discipline, not the checker. Common mapping:
  - RC1/RC7 FAIL → oracle is too trivial; this is a task-design issue that should have been resolved in Step 2a. Consider whether the task concept is genuinely hard.
  - RC2 FAIL → a file, directory, or test name encodes the contract. Rename.
  - RC3/RC4 FAIL → tests check format/existence or depend on tamperable surfaces. Rewrite assertions to assert computed domain values.
  - RC5 FAIL → a reference artifact leaked into solver-visible space. Move expected values into test code.
  - RC6 FAIL → `instruction.md` over-specifies the fix. Rewrite symptoms-only; the Construction discipline listed every signal family that triggers this.

After any fix, rerun `run_static_checks.py` then rerun `collapse_check.py`. Do NOT proceed to the oracle + NOP sanity check with a FAIL — every cycle of oracle investment on a collapse-failing task is wasted.

## Oracle + NOP sanity check (verification, not discovery)

This is a **sanity check**, not a flakiness test. Launch in parallel in separate terminals (no API key needed):
  harbor run -p "tasks/<task-name>" -a oracle
  harbor run -p "tasks/<task-name>" -a nop

Without `-k`, harbor runs exactly one oracle trial. That's the point: a single trial is enough to confirm the plumbing works (Dockerfile builds, test.sh wires up, solve.sh produces artifacts tests accept, NOP baseline is correctly rejected). The 10x stress test belongs in Step 4, after every structural edit is settled — running it here wastes time any later edit would invalidate.

**Expected outcome:** oracle 1.0, NOP 0.0 on the first run. By this point, `run_static_checks.py` and `collapse_check.py` have already verified structural correctness; the oracle + NOP run confirms end-to-end plumbing. A disciplined construction with a correct Dockerfile, matching `solve.sh`, and tests that assert what `solve.sh` actually produces should pass first try.

If either fails, construction missed a plumbing concern:
- Oracle <1.0: `solve.sh` doesn't produce what tests expect, or the Dockerfile doesn't build, or `tests/test.sh` is not wired correctly. Preservation hint: when fixing, keep other gates' invariants in mind — an oracle fix that adds non-determinism will pass 1x but fail Step 4's 10x; a fix that changes solve.sh's outputs may require matching test updates. Then rerun `run_static_checks.py` and `collapse_check.py` (cheap; guards against regressions introduced by the fix), and re-run this sanity check.
- NOP >0.0: tests are too permissive — an empty/default output already passes. This usually traces to an RC3 slip-through (asserting existence instead of computed correctness). Fix by asserting domain-correct values, not format alone. Preservation hint: don't over-tighten. An assertion tightened past what `solve.sh` actually produces will fail oracle 1x. Keep NOP rejected AND oracle accepted simultaneously. Then rerun `run_static_checks.py` and `collapse_check.py`, and re-run this sanity check.

Do NOT run `harbor run ... -a oracle -k 10 -n 10` here. Flakiness hunting is Step 4's job, once every edit is locked in.

## Report and stop

Report ONLY these:
1. Files created under tasks/<task-name>/
2. Discovery-budget confirmation per item
3. Discoverability-gate answers (plus any signal eliminated)
4. `run_static_checks.py` verdict — ideally PASS on first run
5. `collapse_check.py` verdict per RC1-RC7 — ideally PASS on first run
6. Oracle score (1/1) and NOP score (0.0) — ideally on first run
7. Any check that did NOT pass first try — which construction rule was missed, and the minimal fix applied

A clean Step 2b report has zero fixes to describe in item 7. A report with one or two construction-rule slips and minimal fixes is fine. A report with many fixes is a signal that construction discipline needs more attention — not that the checks are working as intended.

Then **stop.** Do not run `validate_submission_zip.py`, `approve_task.py`, or the 10x oracle stress test here — those live in Step 4. Do not produce any ACCEPT / ACCEPT WITH NOTES / REJECT verdict here either; the verdict belongs in Step 4 after the Step 3b review and the approval gate have both run.

If paper checks, static, collapse, and the oracle + NOP sanity check all pass, the task is ready for Step 3b (review). If a reviewer or platform feedback triggers a diagnostic, go to Step 3a first; otherwise go straight to Step 3b.

Authoring spec path: [PASTE THE PATH e.g. specs/block-krylov-resume.md]
Reviewer appendix path: [PASTE THE PATH e.g. specs/block-krylov-resume-reviewer.md]
```

---

## Step 3a (Optional, for Revisions): Cursor — Diagnostics

**Step 3a is for REVISIONS, not for new-task approval.** For a routine new task, go straight from Step 2b to Step 3b. The diagnostics here are heavier harbor / LLM runs and are opt-in by design.

Both `harbor tasks check` (quality check) and `verifier_health.py` are **completely optional** for new tasks. They exist to support revisions — e.g., platform feedback came back, a reviewer requested a specific audit, or post-upload CI flagged something that needs a deeper look.

**Revision / escalation triggers**

- Platform agent trials reported 0/10 while Step 2b's oracle + NOP look healthy → 3a-V (verifier_health).
- A specific test looks chain-dependent, order-sensitive, or potentially flaky → 3a-V.
- A reviewer asked for partial-oracle ablation evidence → 3a-V.
- A reviewer asked for a GPT-5.2 rubric audit, or post-upload feedback points at instruction/test wording → 3a-Q.
- Step 4's 10x oracle stress showed intermittent failures → 3a-V with `--include-repeat-oracle`.

3a-Q and 3a-V are independent. Run 3a-Q alone, 3a-V alone, or both. Skip both entirely for routine new tasks.

**Prerequisites for either sub-step**

- Step 2b's mechanical gates all passed (static_checks, collapse_check, 1x oracle + NOP sanity).
- Task files are unchanged since Step 2b.

**After running a Step 3a sub-step:** rerun Step 2b's mechanical gates on any files that changed (static → collapse → 1x oracle + NOP — not 10x), then go to Step 3b (review) and Step 4 (10x + package + approve). Attach the artifact(s) to `approve_task.py` in Step 4 — see the Step 4 flag table.

### 3a-Q. Quality check (GPT-5.2 rubric audit) — OPT-IN, REVISIONS

Run when a reviewer requested it or you want to pressure-test the instruction/test wording against an LLM judge.

**The user provides the entire quality-check result as input to this step (pasted at the bottom of the prompt).** The agent does NOT re-run `harbor tasks check`; it works from the pasted result. This step is deliberately narrow: route every ❌ fail through the adjudicator first, repair **only** the axes the adjudicator classifies as `task-defect`, and do so without regressing any gate an earlier step has already earned.

```text
1. Parse the quality-check result the user pasted at the bottom of this prompt and write it to `/tmp/<task-name>-qc.json` in the harbor-compatible shape the adjudicator expects:
     {
       "<rubric_axis>": { "outcome": "pass" | "fail", "explanation": "<text>" },
       ...
     }
   For each line of the form `✅ pass - <axis>: <text>` or `❌ fail - <axis>: <text>`:
   - `outcome` is `pass` (✅) or `fail` (❌), lowercase.
   - `<axis>` is the token between ` - ` and the FIRST `:` on that line.
   - `<text>` is everything after that first colon (preserve internal colons, parentheses, quotes verbatim — the adjudicator's SHA digest is taken over this file).
   Preserve every axis the pasted input reports — both passes and fails — so the adjudicator's audit trail is complete. Do not invent axes the user did not provide.

   If the pasted input contains **zero ❌ fail entries**, there is nothing to adjudicate and nothing to repair. Write `/tmp/<task-name>-qc.json` for the audit trail, then skip to step 6.

2. **Check with the adjudicator FIRST — before any task-file edit.** The adjudicator is the authoritative decision on whether a repair is required for each fail; never pre-empt it by editing based on the raw checker text. Run:
     python3 quality_check_adjudicate.py \
         --task-dir tasks/<task-name> \
         --qc-output /tmp/<task-name>-qc.json \
         --out /tmp/<task-name>-quality-check-adjudication.json

   Author `tasks/<task-name>/quality_check_adjudication.json` with one entry per fail. Each entry must include `rubric_axis`, `finding_summary`, and `classification` plus class-specific evidence. Only `task-defect` drives a task-file edit — the other two classifications are resolved by waiver evidence alone:
   - `task-defect` — real gap. **Repair required.** Blocking until repaired. Requires `repair_reference` (commit SHA, PR URL, or `"pending"`).
   - `convention-conflict` — checker remedy contradicts a rule enforced by `run_static_checks.py`, `collapse_check.py`, or the canonical templates in `task-creation.mdc`. **No task edit — waive with evidence.** Requires `enforcing_rule.file` and `enforcing_rule.line`.
   - `unsupported` — finding cites code/fields/behavior that do not exist in the task. **No task edit — waive with evidence.** Requires `negative_lookup.command` and `negative_lookup.expected_stdout`.

   `quality_check_adjudicate.py` exits non-zero whenever any fail is unadjudicated or classified `task-defect`.

3. **Scope-lock before repairing.** Read `/tmp/<task-name>-quality-check-adjudication.json` and enumerate two disjoint lists:
   - axes classified `task-defect` — **the only axes this step may edit task files for**,
   - axes classified `convention-conflict` or `unsupported` — **do not touch any task file for these**; they are resolved by the waiver evidence alone.

   If the `task-defect` list is empty, skip to step 6 — the quality check is resolved entirely through waivers and no task edits are needed. Editing anything to make the raw checker "look cleaner" risks regressing RC6, collapse difficulty, or the `instruction_test_vocabulary` static check for no legitimate quality gain.

4. **Quality-vs-difficulty tension (READ BEFORE EDITING).** Fixing quality findings like `behavior_in_task_description`, `behavior_in_tests`, or `anti_cheating_measures` often tempts you to add specifics to `instruction.md`, test assertions, or runtime checks. The same specificity is exactly what RC6 (instruction spec-completeness) and the collapse/discoverability gate reject. Satisfy the quality check by describing **observable behavior and acceptance criteria**, not by leaking algorithms, fix locations, cause attributions, exact thresholds, or solver recipes. If a `task-defect` cannot be repaired without revealing cause-level detail, the failure is a task-design problem, not a wording problem — restructure the underlying test/oracle/environment instead. Adjudication (as `convention-conflict` or `unsupported`) is the correct response when a fail is hallucinated or contradicts a repo-enforced rule. For convention-conflict / unsupported classifications, the correct response is adjudication evidence, not a task edit.

5. **For each axis classified `task-defect` (and ONLY those), apply the Step 3b preservation discipline** (predict at-risk gates, prefer preservation-safe fixes, label justified regressions):
   a. State the finding and the exact edit. Name the at-risk gates (most quality-check defects impact instruction.md wording → RC6 and `instruction_test_vocabulary`; some impact tests → NOP and RC3/RC4).
   b. Run `python3 collapse_check.py tasks/<task-name>`. FAIL = revert/restructure the edit. WARN = note whether each signal was already present pre-edit. PASS = proceed.
   c. Re-read `instruction.md` honestly — did the edit add algorithm names, schemas, CLI flags, thresholds, file/function locations, cause statements, or step-by-step recipes? If yes, rewrite the edit to stay at symptom/behavior level.
   d. Rerun Step 2b's oracle 1x + NOP sanity check (results from before the edit do NOT carry forward; do not run 10x here — 10x is Step 4's). A preservation-safe edit should re-pass this on the first try; if it doesn't, the edit wasn't actually preservation-safe.
   e. The agent does not re-run harbor. If the user supplies a fresh QC result after the repair (by re-running harbor externally and pasting a new block), re-enter this step from sub-step 1 with the new pasted input; otherwise the adjudication artifact from sub-step 2 is the authoritative quality-check record for this revision.

   **Do not touch any task file for an axis NOT classified `task-defect`.** This is the single rule that operationalizes "without causing any other regression" — broadening the repair scope beyond the adjudicator's decision is the most common source of RC6 / `instruction_test_vocabulary` / NOP regression in this step.

6. Pass the adjudication artifact to `approve_task.py` via `--quality-check-adjudication /tmp/<task-name>-quality-check-adjudication.json` when you run Step 4.

Report:
- `/tmp/<task-name>-qc.json` path (harbor-JSON reconstructed from the pasted input).
- Adjudicator gate (PASS / FAIL) and per-axis classification.
- Explicit `task-defect` list (repaired) vs. `convention-conflict` / `unsupported` list (waived, no edit).
- Per edit: at-risk gates named (from 5a), post-edit `collapse_check.py` verdict, post-edit oracle 1x + NOP scores.
- Final confirmation: "no task file was edited for an axis NOT classified `task-defect`".

Task path: tasks/<task-name>

Quality check result (paste the full ✅/❌ block below):

[USER PASTES THE FULL QUALITY CHECK OUTPUT HERE]
```

### 3a-V. Verifier health (partial-oracle + randomized-order) — OPT-IN, REVISIONS

Run when any of these applies:

- Platform agent trials scored 0/10 while oracle + NOP both look healthy.
- A specific test looks chain-dependent, order-sensitive, or flaky.
- A reviewer asked for partial-oracle ablation evidence.
- Step 4's 10x oracle stress shows intermittent failures (include --include-repeat-oracle in that case).

```text
1. Run the diagnostic:
     python3 verifier_health.py --task-dir tasks/<task-name> \
         --output-json /tmp/<task-name>-verifier-health.json

   The default pass runs randomized-order + partial-oracle ablations on temporary task copies; it does not modify the real task dir. Pass --include-repeat-oracle only when you specifically want the repeated-oracle stress test.

2. If the report exits non-zero, apply the **Step 3b preservation discipline** when fixing (predict at-risk gates, prefer preservation-safe fixes, label justified regressions). Then interpret the result:
   - randomized_order FAIL → a test depends on execution order or shared global state. Fix the test (at-risk gates: NOP if the fix loosens assertions, RC3/RC4 if you weaken domain checks, oracle 1x if the fix changes what tests expect of solve.sh's output). Rerun Step 2b's mechanical gates (static → collapse → 1x oracle + NOP), and rerun verifier_health.py.
   - partial_oracle FAIL (no behavioral failure; all ablations still pass or only compile-break) → the verifier does not discriminate between partial and complete fixes. Fix the tests so a behavioral partial-oracle failure shows up (at-risk gates: same as above; also watch that stronger domain assertions don't accidentally regress oracle 1x by tightening past what the real solve.sh produces). Rerun Step 2b's mechanical gates, and rerun verifier_health.py.
   - repeat_oracle FAIL (only when --include-repeat-oracle was passed) → the oracle is flaky. Fix determinism in solve.sh or the environment (at-risk gates: oracle 1x if the fix changes outputs, RC1/RC7 if the fix substantially changes oracle LOC).

3. For any task-file edit made to fix a verifier-health failure: rerun Step 2b's mechanical gates (static → collapse → 1x oracle + NOP, NOT 10x) before re-running verifier_health.py. Pre-edit evidence does NOT carry forward. The 10x stress re-runs automatically when you reach Step 4. A preservation-safe fix should re-pass every gate on the first try.

4. Pass the JSON report to `approve_task.py` via `--verifier-health /tmp/<task-name>-verifier-health.json` when you run Step 4.

Report: verifier-health decision, blocking failures (if any), any files edited, post-edit Step 2b mechanical-gate result.

## Constraints
- Do not claim any command passed unless it was actually run.
- Show the exact output of each harbor command.
- Do not run `verifier_health.py` concurrently with other harbor runs on the same task path.

Task path: tasks/<task-name>
```

---

## Step 3b: Cursor — Second-Opinion Review (Verify; Fix Only If Construction Missed Something)

Run after Step 2b's mechanical gates and oracle + NOP sanity check all passed (and any Step 3a sub-step you ran, if any).

Step 3b is **LLM-level second-opinion verification**. The mechanical gates (`run_static_checks.py`, `collapse_check.py`) and oracle 1x + NOP already passed in Step 2b because the task was constructed to the documented rules. Step 3b adds concept-level review that checkers cannot do — structural judgement against `@review-and-submit.mdc` §1-7, an LLM-level read of Part A's collapse template, and a paper review of test feasibility (Part B). There are three sub-steps:

1. Structural review against `@review-and-submit.mdc`
2. LLM-level collapse audit (`@difficulty-calibration.mdc` Part A — full template; complements the mechanical `collapse_check.py` that already passed in Step 2b)
3. Per-test feasibility paper review (`@difficulty-calibration.mdc` Part B — flag HIGH-risk tests; escalate to Step 3a-V if needed)

**Expected outcome:** three clean verdicts, no edits, zero dirty-flag. The Construction discipline in Step 2b is spec-aware of every rule Step 3b walks — a disciplined draft should need no corrections here. Step 3b is a second pair of eyes, not a rework phase. If Step 3b consistently needs fixes, the problem is Step 2b construction discipline, not Step 3b's sensitivity.

When Step 3b _does_ find something, it's usually a concept-level blind spot the mechanical checks cannot see — a judgement call about whether the oracle is hard enough in context, whether an assertion is "the only valid answer," whether a test is quietly chain-dependent. For those rare concept-level findings, use the Preservation discipline below to apply a minimal fix without regressing earlier gates.

Step 3b does NOT package the task and does NOT run `approve_task.py`. Those are Step 4. Step 3b also does NOT produce the final ACCEPT / ACCEPT WITH NOTES / REJECT verdict — that is Step 4's output, after the mechanical gate has actually run.

Step 3b also does NOT re-run `run_static_checks.py` or `collapse_check.py` — those already passed in Step 2b. If a Step 3b LLM review forces an edit, the dirty-flag rule below handles re-running the Step 2b mechanical gates on the new state.

### Preservation discipline (read before editing anything in 3b)

Edits in 3b should be rare. When they are needed, they must preserve the gates Step 2b already earned. By the time you're in 3b, the task has already passed a specific set of gates in Step 2b, representing real, earned work:

| Gate                        | Invariant the edit must not violate                                                                                                                                                                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_static_checks.py`      | `task.toml` metadata valid; test.sh matches template; env file count ≥ 20; timeout coherence; dockerfile COPY sources resolve; no build-artifact dirs; instruction doesn't leak `internal_harness_files`                                                               |
| `collapse_check.py` RC1-RC7 | Oracle does real ADD logic (RC1/RC7); names don't predict targets (RC2); tests check domain correctness, not format (RC3); tests aren't tamperable (RC4); no answer-shaped reference artifacts in solver-visible surfaces (RC5); instruction stays symptoms-only (RC6) |
| Oracle 1x (sanity)          | Dockerfile still builds; `solve.sh` still produces the outputs tests accept; test.sh wiring still works end-to-end                                                                                                                                                     |
| NOP                         | Tests still reject the broken baseline — assertions still distinguish correct from empty/default outputs                                                                                                                                                               |

The dirty-flag rule exists to catch regressions; it is the **safety net**, not the default plan. The default plan is that Step 3b finds nothing to fix. When it does find something, **fix it in a way that preserves every gate above**. A regression is a _justified exception_ — rare, explicit, and labelled — not the normal consequence of any 3b fix.

Before every edit in 3b, work through this loop:

1. **Name the finding** you're fixing and the sub-step (1, 2, or 3) that raised it.
2. **Predict the at-risk gates.** Use this edit-risk map:
   - Edit to **`instruction.md`**: risks RC6 (if you add algorithm names, thresholds, CLI flags, file/function locations, step-by-step recipes, or cause attributions); risks `instruction_test_vocabulary` static check (if your wording stops matching what tests assert).
   - Edit to **`tests/`**: risks NOP (if you loosen assertions), RC3/RC4 (if you weaken domain correctness or open tamper surfaces), and the oracle 1x (if you tighten assertions past what solve.sh actually produces).
   - Edit to **`solution/solve.sh`** or **`environment/`**: risks the oracle 1x directly, and may shift RC1/RC7 (adding/removing oracle LOC) or RC5 (introducing reference-artifact files). Environment edits also risk static_checks (dockerfile COPY sources, package hygiene).
   - Edit to **`task.toml`**: risks static_checks (version, metadata fields, tags, codebase_size, `verifier.timeout_sec` ≥ `environment.build_timeout_sec`).
3. **Design the smallest preservation-safe fix.** For each at-risk gate, keep its invariant intact. Most of these invariants are textually checkable — you don't need to rerun the gate to know whether your draft edit would regress it. Examples of textual self-checks:
   - "Did my instruction.md edit add any algorithm name, schema enumeration, CLI flag list, numeric threshold, or file/function location?" If yes → rewrite more symptoms-only before committing (RC6 preservation).
   - "Did my test-file edit relax an exact-value assertion to a superset that the NOP baseline would also satisfy?" If yes → rewrite the assertion or add a second check that NOP still fails (NOP preservation).
   - "Does my new environment file name contain a token that describes what's broken, or that matches an instruction requirement 1:1?" If yes → rename before committing (RC2 preservation).
   - "Did my solve.sh edit add a randomized path, a network call, a timing-dependent operation, or a filesystem race?" If yes → remove the non-determinism before committing (oracle preservation).
4. **Apply the fix.** Then do the self-check from step 3 against the edited file, not the plan.
5. **Only if no preservation-safe fix exists, declare a justified regression.** State: (a) which gate the edit regresses, (b) why no alternative preserves it. For example, "Part A found oracle trivially collapses to a no-op; enlarging it to meet RC7 adds real computation that produces different output than what the current test_outputs.py asserts. Test-file update required alongside the oracle expansion. Regresses: oracle 1x until tests are updated. Justification: RC7 `trivial` cannot be repaired without expanding oracle behavior." Justified regressions trigger the dirty-flag rule as normal.

A 3b finding that can only be fixed by breaking an earlier gate is often a signal that the finding is really a 2b-level issue (a structural problem that should have been caught before oracle time was spent). Take the dirty-flag hit, do the restructuring once, and move on. Do not iterate: if you find yourself breaking gates on each 3b pass, the task is fragile at the structural level and should be redesigned, not patched.

**DIRTY-FLAG RULE.** If any sub-step below edits a file under `tasks/<task-name>/` (`instruction.md`, `tests/`, `solution/`, `environment/`, or `task.toml`), STOP at the end of Step 3b. Go back to Step 2b's "Static checks" section and work forward from there — static checks → collapse_check → **oracle 1x + NOP (sanity, not 10x)** — to confirm the edit didn't regress the mechanical gates or break the plumbing. If you also ran Step 3a, rerun the sub-step(s) you invoked. Pre-edit evidence does NOT carry forward. The forbidden-but-on-disk files (`output_contract.toml`, `quality_check_adjudication.json`, `rubric.txt`, `rubrics.txt`) are NOT part of the dirty-flag set — they are authoring metadata, not solver-visible task content.

The dirty-flag rule is the safety net. The preservation discipline above is the default plan. Preservation-safe edits still trigger the dirty-flag rule (a re-run is cheap insurance), but they should re-pass all gates on the first try; the re-run confirms rather than discovers.

The 10x oracle stress test is deferred to Step 4 and only runs once, after every edit is settled. Do NOT run `harbor run ... -a oracle -k 10 -n 10` here, even on a dirty-flag re-entry. Running 10x now wastes time any later edit will invalidate.

```text
Review the task across the three sub-steps below. Before every edit, apply the Preservation discipline from the Step 3b preamble — predict at-risk gates, design a preservation-safe fix, self-check against the actual edit. Only break an earlier gate as a labelled justified regression when no alternative exists. Produce a Step 3b summary at the end.

Do NOT zip the task, do NOT run approve_task.py, and do NOT run the 10x oracle stress test here — those are Step 4. Do NOT re-run run_static_checks.py or collapse_check.py here — those ran in Step 2b. Track every task-file edit and whether it was preservation-safe or a justified regression.

Follow @review-and-submit.mdc and @difficulty-calibration.mdc for all rules — do not rely on behavioral descriptions in this prompt alone.

### 1. Structural review

Walk @review-and-submit.mdc § 1-7 (Instruction, Environment, Oracle Solution, Verifiers, Task Metadata, Task Structure, Difficulty Calibration). For each section, report PASS / WARN / FAIL with one-sentence justification. Fix any HIGH issue immediately; report MEDIUM with note; LOW alone does not block.

Mandatory sub-checks:
- Compare tests/test.sh against the official platform template in @task-creation.mdc. Standard and UI tasks have different templates — confirm which applies and that the structural parts (control flow, variable names, reward footer) match verbatim.
- Confirm `output_contract.toml` exists at the task root (required by repo conventions; will be excluded from the zip in Step 4).
- Hard FAIL classification: the following are always Hard FAIL, never WARN, regardless of mechanical-gate verdicts: (a) solve.sh edits a path declared in the spec's decoy_manifest; (b) construction_manifest.json is missing when the spec's Construction manifest section names a symbol_table; (c) flipping_point_contract.locations[*].controls_tests lists a test that does not flip when that location is reverted; (d) any solve.sh operation that produces no on-disk change, or whose only on-disk effect is cosmetic comment / marker substitution to satisfy A16 line-count thresholds. See difficulty-calibration.mdc A16 WARN-band policy.

(`run_static_checks.py` and the environment file-count gate already ran in Step 2b. If no edits have happened since, do not re-run them — they passed. Any edit here triggers the dirty-flag rule, which will run them again on re-entry.)

**Edit risk for this sub-step.** Findings here are typically metadata, template compliance, or dockerfile style. Fixes are usually preservation-safe (touching `task.toml` tags or dockerfile comments doesn't regress RC1-RC7 or the oracle). Still apply the preservation-discipline self-check before committing: e.g., if you edit `verifier.timeout_sec`, confirm it still satisfies the `timeout_coherence` static rule; if you rename a file, confirm the rename doesn't regress RC2 (predictability from file names).

Any edit you make here triggers the dirty-flag rule. Label each edit as "preservation-safe" or "justified regression" with one-sentence reasoning.

### 2. Collapse audit (LLM-level)

Run @difficulty-calibration.mdc Part A on the actual drafted files. Report the full template:
- smallest plausible successful patch (in plain English)
- likely editable frontier (files / config blocks the solver will touch)
- requirement-to-file map (each instruction.md requirement → likely destination)
- oracle line count (non-boilerplate)
- discoverability analysis
- red flags
- residual hardness (one paragraph: what remains hard after the prompt honestly states every checked behavior)
- collapse verdict (PASS / WARN / FAIL)

**Oracle reality check (mandatory).** For every non-trivial operation in solution/solve.sh, confirm its target file exists and the operation produces a substantive on-disk change. A sed that targets non-existent markers, or whose only on-disk effect is cosmetic comment substitution to clear A16's line-count threshold, is a Hard FAIL per the §1 sub-check above. The diagnostic: "if I removed this operation, would oracle still score 1.0?" If yes, the operation is cosmetic. Apply the preservation discipline if a fix is needed.

**Discoverability dimension:** patch SIZE (how much work) and patch FINDABILITY (can the agent locate where to work without domain understanding) are both required. A 200-line oracle across 7 files is still trivial if any channel tells the agent where to look.

This is the LLM-level complement to `collapse_check.py` (which already ran mechanically in Step 2b). The mechanical check catches pattern-level collapse; this catches judgement-level collapse. Findings here often require concept-level edits that would have been too expensive to discover only through oracle runs — which is why this sub-step sits in the cheap review phase before any 10x oracle investment.

**Edit risk for this sub-step.** This is the highest-regression-risk sub-step in 3b. Fixes to a WARN/FAIL Part A finding often want to enlarge the oracle, rewrite the instruction, or restructure the environment — exactly the kinds of edits that touch the oracle 1x gate and RC6/RC7. Apply the preservation discipline carefully:
- If the finding is "oracle is trivially localized," resist the temptation to expand solve.sh without updating tests in lockstep — an oracle that now does more work but produces outputs the tests don't assert will regress oracle 1x. Design the oracle expansion and the test assertions together.
- If the finding is "instruction specifies the fix," rewrite symptoms-only without changing what tests expect — the verifier still asserts the same behavior; only the prompt wording changes. This edit is usually preservation-safe against every gate except `instruction_test_vocabulary` (if your new symptom wording uses different nouns than the tests).
- If the finding is "reference artifact in environment," delete the artifact and the oracle path that consumed it together — losing a leaked answer file must not leave solve.sh looking for a path that no longer exists.

Any edit you make here triggers the dirty-flag rule. Label each edit as "preservation-safe" or "justified regression" with one-sentence reasoning.

### 3. Per-test feasibility (paper review)

Walk @difficulty-calibration.mdc Part B for each test function in `test_outputs.py` (or each `test_mN.py`). For each test, report:
- one-sentence summary of what it checks
- single-valid-approach risk (Y/N + why)
- chain-dependency risk (Y/N + why)
- order-sensitivity risk (Y/N + why)
- flakiness risk (timing, races, subprocess without retries, filesystem polling) (Y/N + why)
- niche-technique risk (Y/N + why)

Flag any test that is HIGH risk on any of those dimensions.

If anything looks chain-dependent, order-sensitive, or potentially flaky, **escalate to Step 3a-V (`verifier_health.py`)** before going to Step 4 — do not proceed on suspicion alone. After 3a-V completes and any fix is applied, the dirty-flag rule fires (rerun Step 2b's static → collapse → 1x oracle + NOP first, then resume the workflow at Step 3b sub-step 1 to re-confirm nothing else regressed).

Propose fixes for any HIGH-risk tests. Any test-file edit triggers the dirty-flag rule.

**Edit risk for this sub-step.** Test edits are the most common source of silent NOP regression. Every fix here must preserve the NOP invariant (the broken baseline still fails). Apply the preservation discipline:
- If you loosen an assertion from exact to approximate, confirm the NOP output (missing / empty / default) still fails the loosened assertion. If an empty dict would now pass, tighten from a different angle or add a second assertion NOP cannot satisfy.
- If you add a precondition / setup block to make a test independently runnable, make sure the precondition doesn't accidentally satisfy the test itself — the precondition should set up the inputs, not the expected outputs.
- If you split a chain-dependent test into independent pieces, keep total coverage — a finding the old coupled test caught should still be caught by at least one new test.

Label each edit as "preservation-safe" or "justified regression" with one-sentence reasoning.

### Step 3b summary

Report:
1. Structural review verdict per @review-and-submit.mdc § 1-7 (PASS / WARN / FAIL per section)
2. LLM-level collapse audit (full Part A template)
3. Per-test feasibility flags, and whether Step 3a-V was escalated
4. Edit ledger — for each edit you made, one line: "<file>: <one-line fix summary> — preservation-safe | justified regression (<which gate, why unavoidable>)". If you made no edits, say so explicitly.
5. Next action:
   - If any task file was edited → "Dirty-flag fired. Returning to Step 2b's static_checks / collapse_check / 1x oracle + NOP before Step 4. Not running 10x oracle now. Expect N preservation-safe edits to re-pass on first try; expect M justified regressions to require per-gate re-verification." (N and M come from the edit ledger.)
   - Else if any sub-step is FAIL without an applied edit → "Stopping. Fix flagged issues under the preservation discipline, then restart Step 3b from sub-step 1."
   - Else → "Ready for Step 4 (10x flakiness check + packaging + approval gate)."

Do NOT produce an ACCEPT / ACCEPT WITH NOTES / REJECT verdict here — that is Step 4's output after the mechanical gate has actually run.

Task path: tasks/<task-name>
```

---

## Step 3b→4: Cursor — Dirty-flag re-entry (ONLY if you edited a task file in Step 3a/3b)

Run this after Step 3b **only when** you made any edit under `tasks/<task-name>/` during Step 3a or Step 3b. That edit makes Step 2b's mechanical evidence stale; do not proceed to Step 4 until you re-validate the current working tree state.

```text
You made a task-file edit in Step 3a/3b, so the dirty-flag rule fired. Re-run Step 2b's mechanical chain for the current working tree state, then re-run Step 3b (paper review). Do NOT run the 10x oracle stress test yet.

Run:
  python3 run_static_checks.py --task-dir tasks/<task-name> --version edition_2
  python3 collapse_check.py tasks/<task-name>
  harbor run -p "tasks/<task-name>" -a oracle
  harbor run -p "tasks/<task-name>" -a nop

After those pass again, re-run Step 3b (structural review + Part A + Part B). Only then proceed to Step 4.
```

---

## Step 4: Cursor — Flakiness, Packaging & Approval Gate

Run after Step 3b's summary said "Ready for Step 4" (no dirty-flag, no FAILs). Step 4 has five sub-steps:

1. Oracle 10x flakiness check — the only place the stress test runs, after every edit is settled
2. Generate the submission zip (with FORBIDDEN_ROOT_FILES exclusions)
3. Run `approve_task.py` (which bundles `run_static_checks.py` + `collapse_check.py` + `validate_submission_zip.py` + manifest verification + zip/source parity)
4. Mirror `task.toml` + `instruction.md` into `repo_tests/fixtures/tasks/<task-name>/` so the parity test stays green
5. Produce the final verdict

Decision: **ACCEPT / ACCEPT WITH NOTES / REJECT** — three options only. Do **NOT** produce a SEND FEEDBACK verdict; it is no longer part of this workflow. If the task is unsalvageable through small fixes, REJECT with a one-paragraph note describing what restructuring a future attempt would need.

```text
Run the 10x oracle flakiness check, package the task, run the single approval gate, mirror the task into repo_tests fixtures, then produce the final verdict (ACCEPT / ACCEPT WITH NOTES / REJECT — never SEND FEEDBACK).

## Preconditions

- Step 2b's mechanical gates all passed (static_checks, collapse_check, and the 1x oracle + NOP sanity check).
- Step 3b finished with "Ready for Step 4" (no task-file edits, no FAILs in any sub-step).
- If Step 3a-Q was run: `/tmp/<task-name>-quality-check-adjudication.json` exists.
- If Step 3a-V was run: `/tmp/<task-name>-verifier-health.json` exists.

If any of those is not true, STOP and return to the appropriate earlier step. Do not zip or approve using stale or pre-edit evidence.

## 1. Oracle 10x flakiness check (BLOCKING — runs ONCE at this stage)

This is the only place the 10x oracle stress test runs in the whole workflow. Earlier steps used `harbor run -p ... -a oracle` (one trial, no -k) as a cheap sanity check, because any structural edit downstream would have wasted the 10x investment. By now every mechanical and LLM-level edit is settled, so 10 parallel trials actually mean something.

  harbor run -p "tasks/<task-name>" -a oracle -k 10 -n 10

All 10 trials must score 1.0. If any trial scores below 1.0, the oracle is flaky (non-deterministic solve.sh, environment race, timing dependency, filesystem ordering, network retry, etc.):
- Do NOT just rerun and hope. Identify the source of non-determinism.
- Fix it in `solution/solve.sh`, `environment/`, or the test — whichever is actually racing.
- That fix is a task-file edit → the dirty-flag rule fires. Return to Step 2b's "Static checks" section and work forward (static → collapse → **1x oracle + NOP sanity**). Then go through Step 3b (the three-sub-step review) again to re-confirm nothing concept-level regressed. Only then come back here for another 10x.

Do not run `approve_task.py` with a flaky oracle. The gate won't catch flakiness — it's a one-shot check from the gate's perspective — but shipping a flaky task is worse than shipping no task.

Report: oracle score (X/10). If not 10/10, stop and follow the fix-and-restart loop above.

## 2. Generate the submission zip

The zip must NOT contain any file listed under `validate_submission_zip.FORBIDDEN_ROOT_FILES` (`output_contract.toml`, `quality_check_adjudication.json`, `rubric.txt`, `rubrics.txt`). These files live at the task root for repo tooling but are forbidden in the shipped archive — exclude them explicitly with `-x`:

  cd tasks/<task-name>
  rm -f ../../Task_Ready_To_Submit/<task-name>.zip
  zip -rq ../../Task_Ready_To_Submit/<task-name>.zip . \
      -x '*/__pycache__/*' '*.pyc' '.*' \
      -x 'output_contract.toml' \
      -x 'quality_check_adjudication.json' \
      -x 'rubric.txt' \
      -x 'rubrics.txt'
  python3 ../../validate_submission_zip.py ../../Task_Ready_To_Submit/<task-name>.zip
  cd ../..

If `validate_submission_zip.py` reports `forbidden archive-root file(s) present`, the most common cause is that the `-x` exclusion list above was incomplete — add the missing filename and re-zip. Do NOT continue to the gate with a non-PASS zip validation.

## 3. Run the approval gate

`approve_task.py` re-runs `run_static_checks.py` + `collapse_check.py` (RC1-RC7) + `validate_submission_zip.py` + manifest verification + zip/source parity, and — when attached — strictly validates the verifier-health and quality-check artifacts. (These already passed in Step 2b; the gate re-runs them as the authoritative check against the actual shipped zip.) Pick the one command that matches which Step 3a sub-steps (if any) you actually ran:

  # Routine path — no Step 3a-V, no Step 3a-Q:
  python3 approve_task.py --task-dir tasks/<task-name> \
      --zip Task_Ready_To_Submit/<task-name>.zip \
      --skip-verifier-health

  # Step 3a-V was run (no 3a-Q):
  python3 approve_task.py --task-dir tasks/<task-name> \
      --zip Task_Ready_To_Submit/<task-name>.zip \
      --verifier-health /tmp/<task-name>-verifier-health.json

  # Step 3a-Q was run (no 3a-V):
  python3 approve_task.py --task-dir tasks/<task-name> \
      --zip Task_Ready_To_Submit/<task-name>.zip \
      --skip-verifier-health \
      --quality-check-adjudication /tmp/<task-name>-quality-check-adjudication.json

  # Both 3a-Q and 3a-V were run:
  python3 approve_task.py --task-dir tasks/<task-name> \
      --zip Task_Ready_To_Submit/<task-name>.zip \
      --verifier-health /tmp/<task-name>-verifier-health.json \
      --quality-check-adjudication /tmp/<task-name>-quality-check-adjudication.json

Flag rules:
- `--verifier-health` and `--skip-verifier-health` are mutually exclusive — use exactly one.
- Pass `--verifier-health` or `--quality-check-adjudication` ONLY when the corresponding Step 3a sub-step was actually run.

If `approve_task.py` exits non-zero, report its blocking failures verbatim. Fix the specific files it flagged **under the Step 3b preservation discipline** (predict at-risk gates, prefer preservation-safe fixes, label justified regressions). If the fix touches `instruction.md`, `tests/`, `solution/`, `environment/`, or `task.toml`, the dirty-flag rule fires — go back to Step 2b's "Static checks" section and work forward (static → collapse → **1x oracle + NOP**, NOT 10x), then through Step 3b's three sub-steps again, before retrying Step 4. Preservation-safe fixes should re-pass every earlier gate on the first try; the re-run confirms rather than discovers. The 10x flakiness check at the top of Step 4 runs again when you re-enter Step 4 — that is the correct single place for it, and it will catch any determinism regression the earlier cheap sanity missed. Edits limited to forbidden-but-on-disk files (e.g., regenerating `quality_check_adjudication.json`) do NOT trigger the dirty-flag rule because those files are not part of the shipped task; just re-zip with the same `-x` list and rerun the gate.

## 4. Mirror task to `repo_tests/fixtures/`

After `approve_task.py` exits 0 and before producing the verdict, copy the two
files the zip-name-parity test expects into `repo_tests/fixtures/tasks/<task-name>/`.
The shipped task is now locked (Step 4 is the final gate; later edits restart
from Step 2b), so this is the correct anchor for fixture mirroring.

  mkdir -p repo_tests/fixtures/tasks/<task-name>
  cp tasks/<task-name>/task.toml \
     tasks/<task-name>/instruction.md \
     repo_tests/fixtures/tasks/<task-name>/

Rules:
- Copy verbatim. No edits, no normalization.
- Do not add other files (state JSONs, validation logs, checksums, zips,
  manifests) to the fixture dir — only `task.toml` and `instruction.md`.
- Verify both source files exist before copying. If either is missing
  (e.g. you typoed `<task-name>`), abort and report — do not partially
  populate the fixture dir.

Verify the suite returns to baseline:

  python3 -m unittest discover -s repo_tests 2>&1 | tail -3
  python3 -m unittest discover -s repo_tests 2>&1 \
    | grep -E '^(FAIL|ERROR):' | sort | md5sum

The failure count should be one lower than before this sub-step ran (the
parity test for `<task-name>.zip` flips from FAIL to PASS). The md5 of the
sorted failure list should match the project's recorded baseline. If the
count drops by more than one, or the md5 unexpectedly changes beyond the
parity-test entry, stop and investigate before producing the verdict — a
fixture commit must not silently mask an unrelated test failure.

## 5. Decision

Produce exactly one verdict from these three. Apply the blocking conditions from `@review-and-submit.mdc` § Decision Criteria. SEND FEEDBACK is no longer a valid choice — if the task is unsalvageable through small fixes, REJECT with a redesign note.

- **ACCEPT** — all of the following are true:
  - Oracle 10/10 at 1.0 and NOP 0.0 (Step 2b)
  - `collapse_check.py` PASS overall (every RC1-RC7 PASS, or documented WARN)
  - RC6 is `symptoms-only` or `cause-revealing` (never `spec-complete`)
  - RC7 is `substantive` or `borderline` (never `trivial`)
  - Step 3b LLM-level collapse audit verdict is PASS
  - No HIGH-risk per-test feasibility flag remains unresolved
  - `validate_submission_zip.py` PASS (no forbidden root files in zip)
  - `approve_task.py` exit 0
  - If Step 3a-V was run: PASS with at least one behavioral partial-oracle failure
  - If Step 3a-Q was run: every fail adjudicated as `convention-conflict` or `unsupported` (no `task-defect`)

- **ACCEPT WITH NOTES** — same as ACCEPT, except:
  - `collapse_check.py` returned WARN (not FAIL) with documented residual hardness, OR
  - Step 3b LLM-level collapse audit returned WARN with documented justification, OR
  - Minor mechanical issues remain that do not affect difficulty
  Not allowed when: any RC is FAIL; `verifier_health.py` was run and FAILed; discoverability signals were found but not fixed.

- **REJECT** — any of the following is true and cannot be fixed without restructuring the task:
  - `collapse_check.py` FAIL after attempted fixes
  - Step 3b LLM-level collapse audit FAIL
  - Oracle cannot reach 1.0
  - NOP scores above 0.0 and cannot be brought to 0.0
  - The task fails a hardness axis (Discover, Synthesize, Diagnose, Navigate coupling, Reason beyond training)
  - The concept is unsalvageable through small fixes (would have been "SEND FEEDBACK" under the legacy criteria) — REJECT with a one-paragraph note describing what restructuring a future attempt would need

**Do NOT use SEND FEEDBACK.** It is not a valid verdict in this workflow.

## Required report
1. Overall decision (ACCEPT / ACCEPT WITH NOTES / REJECT — never SEND FEEDBACK)
2. `validate_submission_zip.py` result (and any forbidden-root file the `-x` list caught and excluded)
3. `approve_task.py` exit code
4. Final zip path
5. Fixture mirror confirmation: `repo_tests/fixtures/tasks/<task-name>/{task.toml,instruction.md}` present; post-mirror `repo_tests` failure count and md5 of the sorted failure list (matches the recorded baseline modulo this task's parity test flipping to PASS)
6. Which Step 3a artifacts (if any) were attached, and which approve_task.py flag combination was used
7. Reference back to Step 3b's summary for the upstream review verdicts (do not duplicate them here; just confirm they were consulted)
8. If REJECT: the one-paragraph redesign note (replaces the legacy SEND FEEDBACK)

Task path: tasks/<task-name>
```

---

## Submitting to the Platform

Run this after Step 4's `approve_task.py` exited 0 with a verdict of ACCEPT or ACCEPT WITH NOTES. The validated zip is already at `Task_Ready_To_Submit/<task-name>.zip`.

Verify the archive root contains exactly: `instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/`. The archive root must NOT contain `output_contract.toml`, `quality_check_adjudication.json`, `rubric.txt`, or `rubrics.txt` — these live at the task root for repo tooling but are forbidden in the shipped archive (see `validate_submission_zip.FORBIDDEN_ROOT_FILES`). If any forbidden file is present, go back to Step 4 sub-step 1 and check the zip command's `-x` exclusion list.

Platform upload:

1. Upload zip. Check "Generate rubric". Uncheck "Send to reviewer". Submit.
2. Wait for CI to return the generated rubric.
3. Edit the rubric for accuracy.
4. Uncheck "Generate rubric". Check "Send to reviewer". Submit.

If platform CI or a reviewer flags something after upload, that is a **revision**, not a new task. Go to Step 3a and run only the sub-step(s) the feedback points at, then return to Step 3b and Step 4.
