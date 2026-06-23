# Task skeletons (offline verifier)

Canonical starting points for new tasks. Each skeleton sets
`[environment].allow_internet = false` and installs verifier dependencies
in `environment/Dockerfile` instead of at runtime in `test.sh`.

| Skeleton | Use when |
|----------|----------|
| `Default_Task_Skeleton/` | Standard single-step Python/pytest task |
| `milestone_template/` | Multi-milestone task (`steps/milestone_N/`, `[[steps]]` in `task.toml`) |
| `UI_Task_Skeleton/` | In-progress UI tasks only (new UI building tasks are not accepted) |

Copy the matching skeleton into `tasks/<task-name>/` and edit from there.
See `.cursor/rules/task-creation.mdc` for full construction rules.
