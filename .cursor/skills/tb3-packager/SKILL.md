---
name: tb3-packager
description: "Step 4 final-approval macro for TB3 tasks. Pull when a task has passed Step 2b (with current .step2b-checksum) and Step 3b paper review with no outstanding edits. Walks through the final approval gates: oracle 10x, NOP score 0.0, submission zip validation, approve_task.py exit 0 including instrumentation block emission, and the repo_tests fixture mirror."
disable-model-invocation: true
---

# tb3-packager — Step 4 final-approval macro

## 1. Pre-conditions

Stop if any fails.

- `tasks/<task-name>/.step2b-checksum` exists.
- Step 3b (`tb3-reviewer`) finished with no outstanding FAIL
  findings.
- `python3 task_integrity.py verify tasks/<task-name>` exit 0.
  Exit 1 (stale / missing) → return to `tb3-task-author`
  preflight, then `tb3-reviewer` if any edit happened.

## 2. Final approval gates

Run in order. Stop on the first failure; do not invoke later
gates with stale state.

```bash
harbor run -p "tasks/<task-name>" -a oracle -k 10 -n 10
harbor run -p "tasks/<task-name>" -a nop
```

- Oracle 10x — all 10 trials at 1.0. Any sub-1.0 trial means
  non-determinism; fix in `solution/solve.sh` or `environment/`.
  That edit dirty-flags → return to `tb3-task-author` preflight
  and `tb3-reviewer` re-check before retrying §2.
- NOP must score 0.0.

Build the shipping zip per `commands.md` § Packaging (use the
full `-x` exclusion list there — `__pycache__`, `*.pyc`,
dotfiles, `output_contract.toml`, `quality_check_adjudication.json`,
`construction_manifest.json`, `rubric*.txt`, `CLAUDE.md`,
`AGENTS.md`, `skills.md`, `.cursor/`, `.aider/`, `.continue/`,
`.claude/`).

```bash
python3 validate_submission_zip.py Task_Ready_To_Submit/<task-name>.zip
```

All checks must pass.

```bash
python3 approve_task.py --task-dir tasks/<task-name> \
    --zip Task_Ready_To_Submit/<task-name>.zip \
    --skip-verifier-health
```

Must exit 0. Add `--verifier-health <path>` and / or
`--quality-check-adjudication <path>` per `commands.md` only
when the corresponding Step 3a sub-step was actually run.

## 3. approve_task.py emits the metrics block

On successful approval, `approve_task.py` aggregates
`tasks/<task-name>/.step2b-metrics.jsonl` into the
`## Per-task authoring metrics` block at
`specs/<task-name>-validation-log.md`. Confirm it has the
eight metrics from `docs/exec-plans/instrumentation.md`. The
last two — `cni_references_fired` and `draft_commitments_diff`
— ship deferred (`[]` and `null`); do NOT flag them.

## 4. Mirror task to `repo_tests/fixtures/`

After `approve_task.py` exit 0, copy the parity-test inputs
into `repo_tests/fixtures/`. The tree is locked at this point
(any later edit restarts from Step 2b).

```bash
mkdir -p repo_tests/fixtures/tasks/<task-name>
cp tasks/<task-name>/task.toml \
   tasks/<task-name>/instruction.md \
   repo_tests/fixtures/tasks/<task-name>/
```

For milestone tasks (no root-level `instruction.md`), mirror
`task.toml` plus each milestone's `instruction.md`:

```bash
mkdir -p repo_tests/fixtures/tasks/<task-name>/steps
cp tasks/<task-name>/task.toml repo_tests/fixtures/tasks/<task-name>/
for d in tasks/<task-name>/steps/milestone_*/; do
  m="$(basename "$d")"
  mkdir -p repo_tests/fixtures/tasks/<task-name>/steps/"$m"
  cp "$d"instruction.md repo_tests/fixtures/tasks/<task-name>/steps/"$m"/
done
```

Verbatim copy of those files only — no checksums, state
JSONs, manifests, logs, or zips.

Verify baseline:

```bash
python3 -m unittest discover -s repo_tests 2>&1 | tail -3
python3 -m unittest discover -s repo_tests 2>&1 \
  | grep -E '^(FAIL|ERROR):' | sort | md5sum
```

Failure count should drop by exactly one (the parity test for
`<task-name>.zip` flips to PASS) and the md5 should match the
recorded project baseline. Anything else — stop and report; do
not land a fixture that masks an unrelated regression.

## 5. Final hand-off

Report:

- Oracle 10x score (10/10 at 1.0).
- NOP score (0.0).
- `validate_submission_zip.py` exit code.
- `approve_task.py` exit code.
- Metrics block confirmed at `specs/<task-name>-validation-log.md`.
- Fixture mirror confirmed; post-mirror failure count and md5.

Then say verbatim:

> Step 4 complete. Submission zip at
> `Task_Ready_To_Submit/<task-name>.zip`. Validation log updated
> with metrics block at
> `specs/<task-name>-validation-log.md`.

Direct the user to ship the zip per the team's submission process
(see `workflow-prompts.md` § "Submitting to the Platform"). Do not
upload from the agent.
