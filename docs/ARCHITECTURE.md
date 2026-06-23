# ARCHITECTURE — short codemap for the TB3 harness

This is a one-page map of which file owns which layer. For policy see
`AGENTS.md` and `.cursor/rules/`; for commands see `commands.md`; for
conventions see `REPO_CONVENTIONS.md`. This file is not the place for
any of those.

## Task spec layer (Step 1 / 2a)

- `specs/<task>.md` — Authoring Brief + Reviewer Appendix +
  Triviality Ledger + Per-gate Pitfall Inventory + Initial Draft
  Commitments. Pre-commitment artifact for the task.
- `specs/<task>-validation-log.md` — attempt history, gate failures,
  dirty-flag triggers, CNI references, draft-commitment drift.
- `specs/.<task>-state.json` — `validate_loop.py` state machine.
- `specs/README.md` — schema documentation for the above.
- `validate_loop.py` — runs Step 2a; gates the spec.
- `lint_spec.py` — checks the new mandatory sections.

## Task implementation layer (Step 2b)

- `tasks/<task>/` — the task itself.
  - **Single-step task layout:**
    - `instruction.md` — symptoms-only public contract.
    - `task.toml` — metadata (category, difficulty, `number_of_milestones = 0`, …) plus `[environment].allow_internet = false`.
    - `output_contract.toml` — declared outputs and schema. Local-only;
      banned in submission zips.
    - `environment/` — code under test. No golden answers, no hints,
      no walkthroughs (enforced by `environment_hidden_instructions`
      static check). No AI-specific filenames (`CLAUDE.md`, `skills.md`, …).
    - `solution/solve.sh` — oracle implementation.
    - `tests/test.sh` and `tests/test_*.py` — verifier.
  - **Milestone task layout** (canonical, `task.toml` `version = "2.0"`
    with `[[steps]]` blocks; see `task-creation.mdc` "Milestone task"):
    - `task.toml` — metadata + `[[steps]]` blocks (one per milestone).
    - `environment/` — shared across all milestones.
    - `steps/milestone_N/` — per-milestone content. Contains
      `instruction.md`, `tests/{test.sh, test_mN.py}`, and
      `solution/{solve.sh, solveN.sh}`. The container filesystem
      persists across milestones.
    - NO root-level `instruction.md` / `tests/` / `solution/` /
      `milestones.md` / `milestone_X.md` (deprecated layout).
  - `.step2b-checksum` — local generated state (see
    REPO_CONVENTIONS.md § "Local generated state").

## Static / collapse layer (Step 2b gates)

- `run_static_checks.py` — instruction, dockerfile, test layout,
  output contract, hidden instructions, milestone language.
- `collapse_check.py` — oracle locality, frontier concentration,
  grep resistance.
- `verifier_health.py` — verifier shape sanity.
- `ci_checks/` — focused single-purpose checks (canary, dockerfile
  references, test sanity, etc.) usable independently of the umbrella.
- `task_integrity.py` — shared checksum module used by both
  `scripts/check-task.sh` and `approve_task.py`.

## Packaging / approval layer (Step 4)

- `scripts/check-task.sh` — one-command preflight (static + collapse
  + tmp-zip-validate + checksum stamp). Not Step 2b PASS.
- `validate_submission_zip.py` — validates a built submission zip.
  Owns `FORBIDDEN_ROOT_FILES`, `BANNED_AI_FILENAMES_CI`, and
  `BANNED_AI_DIRECTORY_NAMES_CI`.
- `approve_task.py` — final approval. Verifies `.step2b-checksum`
  before packaging.

## Task skeletons

- `skeleton/Default_Task_Skeleton/` — standard offline verifier template.
- `skeleton/milestone_template/` — milestone layout + offline per-step runners.
- `skeleton/UI_Task_Skeleton/` — UI offline template (new UI tasks not accepted).

## Agent guidance layer

- `AGENTS.md` — only always-on file. Routing + must-fire bullets.
- `docs/ARCHITECTURE.md` — this file.
- `.cursor/rules/00-authoring-critical.mdc` — agent-requested
  expanded discipline.
- `.cursor/rules/{task-creation,idea-validation,
   difficulty-calibration,review-and-submit}.mdc` — deep references.
- `workflow-prompts.md` — Step 1–4 process + embedded Ralph discipline.
- `commands.md` — canonical command reference.
- `REPO_CONVENTIONS.md` — durable conventions and waivers.
- `CNI.md` — backlog with promotion + demotion policy.
- `skills/` (path locked in phase 2) — opt-in workflow macros.

## Test layer

- `repo_tests/` — regression coverage for every mechanical gate.
- `repo_tests/fixtures/` — fixture tasks with pinned static-check
  results (`COMMON_STATIC_PASS_MESSAGES` in `repo_tests/cases.py`).
