# Repo Tooling Regressions

Run the suite with:

```bash
python3 -m repo_tests
```

These tests pin current checker behavior against the checked-in task fixtures under `repo_tests/fixtures/tasks/` and the archived Harbor evidence under `jobs/`.

The active authoring workspace remains `tasks/`; fixture tasks live outside it on purpose so authors do not copy negative examples into new submissions.

Any future fix for a tooling false positive or false negative should update the relevant expectation here in the same change.
