# AGENTS.md

Terminal-Bench 3.0 Edition 2 task-authoring harness. Unit of work: a task
under `tasks/<task-name>/`. New here? Read `docs/ARCHITECTURE.md` first.

## Where to look

- Layout: `docs/ARCHITECTURE.md`.
- Before any task edit: pull `.cursor/rules/00-authoring-critical.mdc`.
- Authoring: `task-creation.mdc`. Idea validation: `idea-validation.mdc`.
- Review: `review-and-submit.mdc`. Hardness: `difficulty-calibration.mdc`.
- Commands: `commands.md`. Workflow: `workflow-prompts.md`. Conventions: `REPO_CONVENTIONS.md`.

## Must-fire bullets (every interaction)

1. Every `task.toml` must include `[environment] allow_internet = false`; verifier deps go in `environment/Dockerfile`, not runtime installs in `test.sh`.
2. Never claim PASS / READY / APPROVED / SUBMIT without command output as evidence.
3. Cheap gates first: `run_static_checks.py` → `collapse_check.py` → oracle 1x → NOP. No oracle 10x in Step 2b.
4. Don't invent paths, `task.toml` fields, or commands from memory; open the file or `commands.md`.
5. After any task-file edit, prior Step 2b evidence is stale. Rerun cheap gates. `approve_task.py` refuses to package on checksum mismatch.
6. One-command preflight: `./scripts/check-task.sh tasks/<task-name>`. Preflight only — oracle 1x and NOP still required for Step 2b PASS.
7. Milestone tasks use the canonical `steps/milestone_N/{instruction.md, tests/, solution/}` layout with `task.toml` `version = "2.0"` and matching `[[steps]]` blocks. The deprecated root-level `instruction.md` / `tests/` / `solution/` / `milestones.md` shape is rejected — see `task-creation.mdc`.
8. New starts of multi-container or UI building tasks are no longer accepted; in-progress instances may finish.
9. After creating or revising a task and writing the submission zip, run `./scripts/cleanup-task-docker.sh <task-name>` to stop Harbor containers and prune Docker build cache so local runs do not keep the laptop busy.
10. Non-trivial tasks need `environment/.dockerignore` in the task folder and in the submission zip (hidden dotfile; see `task-creation.mdc`). A zip missing `environment/.dockerignore` is a packaging defect when the task dir has one.

## Forbidden in submissions

`output_contract.toml`, `quality_check_adjudication.json`, `construction_manifest.json`, `rubric*.txt`, `.step2b-checksum`, and any AI-scaffolding filename (`CLAUDE.md`, `AGENTS.md`, `skills.md`, `.cursor/`, `.aider/`, `.continue/`, `.claude/`) at any archive depth. See `REPO_CONVENTIONS.md`.
