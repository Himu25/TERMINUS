Idea Creation:-

Follow this guidelines and give me 10 unique ideas that are not repeated in the tasks and should have low risks and should follow @IDEAS.md @.cursor/rules/difficulty-calibration.mdc @.cursor/rules/idea-validation.mdc and should fall in the range below:
1)Automated or AI-generated tasks.
2)Synthetic or spam submissions.
3)Templated content with little to no originality.
4)Tasks copied from previously accepted work with only minor modifications.
5)Low-effort or otherwise non-compliant submissions.
6)All submissions are expected to be original, unique
and language :- Rust go
Also please mention category of the each idea and
Note:- Moving forward, Software Engineering and Debugging category tasks can no longer be submitted.

---

create task according to @@.cursor/rules

1. userns-idmap-ownership

- *Category:* system-administration
- *Languages:* Rust, Go

*Concept:* A rootless container runtime (Go launcher, Rust file-prep helper) sets up user-namespace UID/GID mappings from subuid/subgid ranges plus an idmapped mount. After a nested unshare and a setgid-directory copy, files created inside the container show the wrong host owner, the setgid bit drops on some paths, and a supplementary group silently vanishes for the workload.

*Why hard:* Correct ownership requires coordinating the subuid/subgid range arithmetic, the order of writing uid_map/gid_map/setgroups, the idmap translation, and the nested re-mapping — each in a different module; the obvious single-site fix (widen the map) re-breaks the nested case.

*Why unique:* No namespace/idmap task exists; unrelated to grandchild-exit-leak / pipe-close-shadow (wait & FD lifecycle, not UID translation).

*Low risk:* Opus-weak (kernel namespaces; ownership is a notorious execution-discipline trap). Verified by inspecting resulting ownership/mode in a fixture rootfs against a simulated mount table — deterministic, offline.

---

make sure task align with these files docker environment.mdc dockerfile and image best practices.mdc @workflow.md and it must uses approved canonical image and remove workdir = app it is not required in non-milestone task

---

⁠Infrastructure failures (tmux crashes): 2–3 of the GPT-5.2 runs failed due to tmux not running or crashing. This is typically caused by missing tmux and/or asciinema in your Dockerfile. Make sure both are installed:
dockerfile
RUN apt-get update \
&& apt-get install -y --no-install-recommends tmux asciinema \
&& rm -rf /var/lib/apt/lists/\*
⁠GPT-5.2 scored 0%: Because most of its runs were infrastructure failures (not genuine task failures), the system can't confirm solvability from that model's perspective.

Fix the tmux/asciinema installation in your Dockerfile so GPT-5.2 runs don't crash on infrastructure, and the solvability check should pass on resubmission.

---

@writing_tests.mdc @reviewer_checklist.mdc @instructions_prompt.mdc @ci_checks.mdc Review this task according to these files, and whatever issues comes, fix them.

---

remove canary string if any and also please use approved canonical images then generate the zip file for submission

---

generate copy paste UI submission rubrics for this task here in chat only(codebox) Following @TASK_PROPOSAL_RUBRIC.md @web/TASK_PROPOSAL_RUBRIC.md

---

Kindly consider that you don't expose any hint or implementation plan for The agent

# review

This task was previously evaluated using GPT-5.2 and Opus 4.6, and it met the required difficulty standards at that time. However, with the updated evaluation process now using GPT-5.5 and Opus 4.8, the task is being classified as trivial. Could you please increase its complexity and difficulty while ensuring it continues to satisfy all checklist requirements and quality guidelines