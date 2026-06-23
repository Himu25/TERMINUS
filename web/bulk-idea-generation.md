# Option B — Goal-Sized Seed Bank Generation

Use this prompt when you want the website model to build a **large bank of hard seed ideas** for Step 2a. The bank is sized to the **requested final output after Option A**, not to a fixed raw count like 25-per-category, 100 total, or 30 surfaced survivors.

**Default assumption:** if the user does not specify a target, assume the goal is **150 Step-2a-ready seeds after Option A**.

This is prompt **1 of 2** for Step 1:

1. **Option B** builds a compact, self-screened seed bank.
2. **Option A** (`option-a-seed-refinement.md`) normalizes, strengthens, decontaminates, and returns the final Step-2a-ready bank.

The output of this file is a single markdown document you save as a downloadable `.md`. That file becomes the input to Option A.

---

## Default two-prompt workflow

Use this flow unless you have a strong reason to do something narrower.

- **Prompt 1 — Option B**: generate a **goal-sized** seed bank in the four Opus-weak categories.
- **Prompt 2 — Option A**: turn that seed bank into the **final Step-2a-ready bank** at the requested size.

The two-prompt default is optimized for **bank yield**, not for producing a tiny finalist list.

---

## Default invocation

Attach this bundle (`chatgpt-task-authoring-playbook.md`, `implementation-collapse-audit.md`, `terminal-bench-task-creation.md`, `TASK_PROPOSAL_RUBRIC.md`, and this file) to the chat.

Then say:

> Run **Option B** from `bulk-idea-generation.md` in **goal-sized opus-weak mode**. The final target after Option A is **150 Step-2a-ready seeds**. Use the four Opus-weak categories, keep the bank category-balanced, keep topology families distinct within category, and return one downloadable `.md` seed-bank file.

If you want a different final bank size, replace `150` with your target.

---

## Why the default is the four Opus-weak categories

Current frontier chat models are usually not limited by broad domain familiarity. They fail more often on:

- **wrong source of truth**
- **destructive-if-repeated phases**
- **wrong format / wrong place artifacts**
- **long-horizon state threading**
- **shallow verification**
- **hidden-state / low-observability debugging**
- **edge-case inputs the obvious test misses**

That makes these four categories the default bank generator surface:

1. `system-administration`
2. `security`
3. `debugging` (**systems substrate only**)
4. `scientific-computing`

Only use the full nine-category sweep when you can name the **specific execution/coherence/verification failure mode** that keeps an Opus-strong category hard.

---

## Category attack surface to prefer

### `system-administration`

Prefer ideas built around:
- live state reconciliation
- namespace / mount / cgroup / device-node state
- restore / replay / migration under concurrent load
- destructive administrative phases that are unsafe to repeat
- misleading status tools that validate only counts, bootability, or surface health

### `security`

Prefer ideas built around:
- authority splits and capability confusion
- revocation / freshness / lineage drift across restore or reload
- split decode / split policy authorities
- binary or protocol predicates recovered from behavior rather than named standards
- verifier-bypass bait where the local checker validates the wrong invariant

### `debugging`

Only use debugging ideas with a real systems substrate:
- ABI / layout / binary / loader / rebuild coupling
- asynchronous processes and wait discipline
- replay / rollback / restore / catchup workflows
- causal chains where an early state choice becomes self-hiding later
- low-observability evidence such as `strace`, `readelf`, `/proc`, `dmesg`, pcaps, raw state files, or hex dumps

### `scientific-computing`

Prefer ideas built around:
- checkpoint / resume semantics
- conflicting numerical-policy authorities
- reduction ordering / FP non-associativity
- solver / cache / operator reuse under changed geometry or policy
- plausible-but-wrong outputs where stability alone is a misleading check

---

## High-value hardness levers

Ideas in this bank should preferentially realize the following levers:

1. **Multi-source-of-truth traps** — several state surfaces look authoritative, but only one reconstruction is canonical.
2. **Destructive-if-repeated phases** — restore, migration, compaction, signing, or repair steps mutate the evidence surface.
3. **Premature-completion bait** — a local check flips green before the real invariant is satisfied.
4. **Long-horizon state-threading** — an early decision silently shapes a much later failure.
5. **Wrong-format / wrong-location artifacts** — the content may look right, but the runtime or verifier trusts a different artifact.
6. **Verifier-bypass bait** — the visible checker covers the wrong property.
7. **Variant ladders** — multiple build/runtime arms must remain valid, so deleting one path is not a real fix.
8. **Not-waiting for long-running processes** — migration, rebuild, compaction, packaging, or replay looks done before durable completion.
9. **Terminal-state corruption** — a legitimate debugging step can poison the terminal or interactive state.
10. **Edge-case inputs** — empty controls, duplicate identities, stale caches, restart boundaries, reorder windows, mixed generations.

The strongest seeds usually combine one primary lever with one or two reinforcing levers.

---

## Goal-sized mode semantics

In **goal-sized opus-weak mode**:

- Do **not** use a fixed quota like 25-per-category.
- Size the bank to the **requested final output after Option A**.
- Default to **150 final Step-2a-ready seeds** if the user does not specify a target.
- Generate a **category-balanced** bank across the four Opus-weak categories.
- Prefer **narrower subsystem framings** over filler if a category starts repeating itself.
- Keep **Topology** distinct within each category.
- Surface mostly **bank-ready** seeds, with a limited minority of **repairable** seeds.

### Category balance rule

Aim for broad balance across the four default categories. Do not let one category dominate unless you explicitly note that another category saturated and had to be backfilled.

### Status rule

Each seed must be labeled as one of:

- `bank-ready` — already good enough to survive into Option A with only normalization or ranking changes
- `repairable` — the core is strong, but one specific weakness still needs one strengthening move

Do **not** surface obvious filler, obvious mediums, or undeveloped placeholders just to hit the count.

### Repairable cap

Repairable seeds are allowed, but they should remain the minority. If too much of the bank is repairable, the bank is weak.

---

## Self-screening bar for every surfaced seed

Every surfaced seed must already satisfy all of the following:

1. **Symptoms-only framing**
   - no named fix path
   - no cause-revealing wording
   - no spec-complete contracts

2. **Exactly 3 concrete discoveries**
   - scenario-specific
   - codebase/runtime level
   - not generic family-level filler

3. **All 5 hardness axes plausibly pass**
   - Discover
   - Synthesize
   - Diagnose
   - Navigate coupling
   - Reason beyond training

4. **Distinct Topology token within category**

5. **Evidence basis is assigned**
   - one trajectory tag: `Execution`, `Coherence`, or `Verification`
   - optional command-level tag: `none`, `not-waiting`, `terminal-crash`, or `edge-cases`
   - one cluster tag: `Complex-System-Builds`, `Long-Horizon-Coherence`, `Robust-Verification`, or `Adversarial-Creative-Reasoning`

6. **At least 2 exploits from {1,2,3,4,5,6} are scenario-realized**
   - ladders and command-level exploits can amplify but do not replace the need for core exploit realization

7. **Honest hardness estimate stays in the hard band**
   - if the strongest concrete draft still looks like a medium or a local patch, reject or strengthen before surfacing

---

## RC6 discipline for protocol / primitive surface

If a seed relies on a protocol, cryptographic primitive, binary format, or similarly named surface that would collapse the drafted task if named directly, add a compact `RC6 discipline` note naming what must stay out of the eventual instruction.

The point is not to hide the entire domain. The point is to avoid turning the drafted task into a named-spec transcription exercise.

---

## Optional modes

### Extended nine-category mode

Use only when the user explicitly wants the full 9-category sweep **and** gives a one-sentence reason naming the failure class that keeps the extra categories hard.

Example:

> Run **Option B** from `bulk-idea-generation.md` in **goal-sized extended mode**. The final target after Option A is **150 Step-2a-ready seeds**. Include the Opus-strong categories only when each seed names the execution/coherence/verification failure mode that keeps it hard.

### Narrow-domain mode

Use when the user already knows the subsystem families they want.

Example:

> Run **Option B** from `bulk-idea-generation.md` in **goal-sized narrow-domain mode**. The final target after Option A is **150 Step-2a-ready seeds**. Use these domains: `lsm storage engines`, `wasm runtimes`, `netcode rollback`, `checkpointed PDE solvers`.

### Fast mode

Fast mode is allowed, but it is not the default. If used, the bank must still remain topology-distinct and category-balanced. Use fast mode only when the user explicitly prioritizes speed over bank quality.

---

## Required output schema

The output must be a single markdown document using this exact structure.

````markdown
# Bulk Idea Seed Bank

Generated by Option B. This file is the input to Option A.

Generator metadata:
- Mode: `<goal-sized-opus-weak | goal-sized-extended | goal-sized-narrow-domain | fast>`
- Final target after Option A: `<e.g. 150>`
- Total seeds in this file: `<count>`
- Categories/domains: `<comma-separated list>`
- Self-screened: `<yes | no>`

---

## Category: `<name>`

### 1. `<short title>`
- **Status**: `<bank-ready | repairable>`
- **Topology**: `<3-6 word phrase>`
- **Symptom framing**: `<one sentence, symptoms-only>`
- **Evidence basis**: `trajectory=<Execution|Coherence|Verification>; command_level=<none|not-waiting|terminal-crash|edge-cases>; cluster=<Complex-System-Builds|Long-Horizon-Coherence|Robust-Verification|Adversarial-Creative-Reasoning>`
- **Discoveries**:
  - `<discovery 1>`
  - `<discovery 2>`
  - `<discovery 3>`
- **Exploit anchors**:
  - `Exploit <N>: <scenario-specific realization>`
  - `Exploit <N>: <scenario-specific realization>`
- **Hardness note**: `<one sentence on why this stays hard>`
- **Main rejection risk**: `<one sentence>`
- **Strengthening move**: `<one sentence, or none>`
- **RC6 discipline**: `<only if needed; otherwise omit>`

### 2. `<next seed>`
...

---

## Coverage summary

- Category counts: `<counts by category>`
- Status counts: `<bank-ready=?, repairable=?>`
- Evidence-basis distribution: `<counts>`
- Topology collisions removed during self-screening: `<count>`
- Notes on category backfills or saturation: `<if any>`
````

---

## Operating rules

1. **Do not pad.** If a category starts repeating topology families, narrow the subsystem angle instead of cloning templates.
2. **Do not collapse into a tiny bank.** The whole point of this file is to produce enough strong material that Option A can return the requested final bank size.
3. **Prefer compact cards over essay blocks.** The bank needs to stay usable as an attachment in the second prompt.
4. **Stay in hard-only territory.** If a seed is honest-but-medium, either strengthen it or reject it.
5. **Be explicit about shortages.** If you truly cannot fill the requested count honestly, say which categories saturated and why. Do not hide that by padding.

---

## Recommended default prompt text

Use this exact wording as a safe default:

> Run **Option B** from `bulk-idea-generation.md` in **goal-sized opus-weak mode**. The final target after Option A is **150 Step-2a-ready seeds**. Use the four Opus-weak categories, keep the bank balanced, keep Topology distinct within category, keep most seeds `bank-ready`, and return one downloadable `.md` seed-bank file.

---

## What happens next

1. Save the Option B output as a `.md` file.
2. Attach that file together with the bundle.
3. Run **Option A** from `option-a-seed-refinement.md` in **step2a-bank mode**.
4. Use the resulting Step-2a-ready bank inside Cursor to start idea validation and drafting.

Do not stop at Option B unless the user explicitly wants raw seeds only.
