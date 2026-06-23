Idea Creation:-
Follow this guidelines and give me 10 unique ideas that are not repeated in the tasks and should have low risks and should follow @IDEAS.md @.cursor/rules/difficulty-calibration.mdc @.cursor/rules/idea-validation.mdc and should fall in the range below
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

create task according to @@.cursor/rules 7. forced-alignment-phoneme-bind
Category: machine-learning
Languages: Rust, Go

Concept: A speech-training lab replays utterances through forced phoneme alignment. Alignment-boundary counts, duration-binding rows, and OOV-survivor tallies disagree with transcript replay after dialect and truncation scenarios.

Why unique: No speech-alignment ML task exists. Distinct from tokenizer-regression-reproduction and multilingual-prep-throughput (debugging category).

Low risk: Alignment outputs are checkable against golden phoneme lattices in fixtures; no audio I/O at verify time; fresh domain reduces templated-RAG similarity.

---

make sure task align with these files docker environment.mdc dockerfile and image best practices.mdc @workflow.md  and it must uses approved canonical image and remove workdir = app it is not required in non-milestone task

---

•⁠ ⁠Infrastructure failures (tmux crashes): 2–3 of the GPT-5.2 runs failed due to tmux not running or crashing. This is typically caused by missing tmux and/or asciinema in your Dockerfile. Make sure both are installed:
dockerfile
RUN apt-get update \
&& apt-get install -y --no-install-recommends tmux asciinema \
&& rm -rf /var/lib/apt/lists/\*
•⁠ ⁠GPT-5.2 scored 0%: Because most of its runs were infrastructure failures (not genuine task failures), the system can't confirm solvability from that model's perspective.

Fix the tmux/asciinema installation in your Dockerfile so GPT-5.2 runs don't crash on infrastructure, and the solvability check should pass on resubmission.

---
