### FILEPATH: /sprints/SW_way_of_working/sprint_plan.md

**Sprint Goal:** Stop re-authoring the way of working per repo. Extract loop-orchestrator's
Claude Code workflow layer — the `/resume` → `/handoff` → `/critic-gate` → `/ship` protocol, the
critic agents, the Global Conventions, the SessionStart cursor hook — into a **Claude Code
plugin** published from a new `glunk-works/claude-workbench` repo, and adopt it here first.
Closes **#19** ("adopt the working method"), and **retires BI-D3** by making the plugin repo the
central conventions home it called for.

The DRY rule this sprint exists to establish: **a shared skill may never name a repo-specific
value.** If it needs one it reads `.ai/project.yml`; if it cannot be expressed there, it does not
belong in the plugin. Every literal removed from a skill becomes a schema key, and a repo-local
override of a shared skill is a **bug report against the schema**, not a fork.

**bounty-infra is the pilot, deliberately** (BI-D13). It has an empty `.claude/`, so it risks
nothing, and it is a *different shape* from loop-orchestrator — Python **plus** OpenTofu, a
4→8-check ruleset, no `architect-review` gate — which is exactly what forces the parameterization
to be real rather than loop-orchestrator-flavored. loop-orchestrator keeps its working local
copies untouched during this sprint; that duplication window is intentional and closes in SW-2.

**Out of scope:**
- **loop-orchestrator's own migration.** Its Phase-4 sprint (deleting its local skills/agents,
  adopting the plugin, and splitting its 30 KB `CLAUDE.md`) is planned **in that repo, after**
  SW proves portability here. Writing that plan now would be writing it blind — its content is
  largely "whatever SW-1 discovers." See *Follow-on* below.
- **Automating plugin installs.** Adoption is three committed files and a one-time trust prompt.
  No bootstrap script until there is a third or fourth consumer to justify one.
- **`mutation-triage` and `live-verify`.** These encode loop-orchestrator's internals — mutmut,
  and a DEFERRED_VERIFICATION V-run against a live GitHub scratch repo needing per-run spend
  authorization. They stay local there (BI-D12). Shipping them would make the plugin's own rule
  false on day one.
- **Changing any workflow, ruleset, or CI job here.** SW is docs + agent config only. It touches
  no `.github/workflows/**`, no `infra/**`, no `src/**`.
- **Retro-fitting `global-bootstrap` / `scope-core`.** They adopt after loop-orchestrator, when
  the schema has survived two genuinely different repos.

**Context — decisions locked this pass (owner-confirmed, 2026-07-22):**
**BI-D10** plugin distribution, tag-pinned · **BI-D11** `.ai/project.yml` is the parameterization
seam · **BI-D12** portable-core-only scope · **BI-D13** bounty-infra pilots. All four are in
`docs/hardening_roadmap.md`; **BI-D10 supersedes BI-D3 entirely**.

---

## The finding that shapes the sprint

The conventions text already exists in **three** places, and none of them is authoritative:

```
loop-orchestrator/.ai/context/conventions.md          <- edited by hand
loop-orchestrator/src/.../scaffold/templates/CLAUDE.md <- read at RUNTIME by Python
bounty-infra/CLAUDE.md -> raw.githubusercontent URL    <- fetched, uncacheable, unpinnable
```

The third is the worst of them: a network fetch on a mutable `main`, which cannot be prompt-cached
and cannot be pinned. The plugin dissolves it. **The second it does not dissolve** — `scaffold`
is a non-Claude-Code consumer (`writer.py:99` reads the packaged template off disk to inject into
managed repos), so a copy must keep shipping inside loop-orchestrator's wheel. That copy gets a
**drift guard**, not a deletion (Task 6).

The second finding: the coupling in the skills is **values, not logic**. Grepping all 7 skills and
7 agents for repo-specific strings returns check-name lists, `hatch run …`, `docs/migration_roadmap.md`,
and the frozen review header — no branching on repo identity anywhere. That is why a flat
`project.yml` is sufficient and a templating engine is not.

---

## Target architecture

| Layer | Lives in | In context | Owner |
|---|---|---|---|
| **Behavior** — skills, agents, hooks, conventions | `claude-workbench` plugin | descriptions only; bodies on demand | upstream, never edited downstream |
| **Contract** — the values behavior needs | `.ai/project.yml` | always (small) | the repo |
| **Local truth** — what this repo *is* | `CLAUDE.md`, `.ai/context/`, `.ai/next-steps.md` | CLAUDE.md always | the repo |

```
glunk-works/claude-workbench
  .claude-plugin/marketplace.json
  plugins/way-of-working/
    .claude-plugin/plugin.json
    skills/   resume/ handoff/ critic-gate/ archive-sprint/ ship/ pr-checks/ retro/
    agents/   architect.md coder.md security-critic.md docs-consistency.md
    hooks/    hooks.json + ai-cursor-banner.sh
    reference/ conventions.md  workflow.md  project-schema.md
  docs/decisions.md            # WB-D* log
```

---

## Tasks

### Task 1 — Verify the plugin contract before writing any of it

**Do not build against remembered schema.** Confirm, against current Claude Code documentation:
the `marketplace.json` and `plugin.json` field names and required keys; the plugin subdirectory
names (`skills/`, `agents/`, `hooks/`); the `hooks.json` shape and whether `${CLAUDE_PLUGIN_ROOT}`
is the correct interpolation for a hook script path; and the exact settings keys
`extraKnownMarketplaces` / `enabledPlugins` including whether the plugin reference is
`name@marketplace`.

This repo has paid for guessing at vendor shapes twice already — the annotated-tag-object that
made `git/ref/tags/<tag>` return a non-commit SHA, and HackerOne's `scope_exclusions` living on a
separate endpoint from `eligible_for_submission`. Same discipline: **verify the vendor surface,
don't model it from memory.**

*Acceptance:* a short written note of the confirmed schema, with its source, in the SW-1 PR
description. If any key differs from what this plan assumes, the plan is wrong and gets amended —
not worked around.

### Task 2 — Stand up `glunk-works/claude-workbench`

Public repo. `protected-integration-branches` ruleset mirroring this repo's field-for-field
(`pull_request` + `deletion` + `non_fast_forward`, `bypass_actors: []`,
`required_approving_review_count: 0`). Plugin skeleton per Task 1's confirmed schema.
`docs/decisions.md` seeded with **WB-D1..D4** (the four BI-D10..D13 decisions restated as that
repo's own).

**Move `conventions.md` in verbatim** — byte-identical to loop-orchestrator's
`.ai/context/conventions.md` at the commit SW starts from, so the first diff of the drift guard
in Task 6 is empty and any later difference is a real, reviewable change rather than transcription
noise.

`workflow.md` moves in too, with its loop-orchestrator-specific paragraphs (the
`feat/mcp-langgraph-migration` historical note, the sprint-27 Task 8 narrative) **replaced by**
schema references — the *rule* is portable, the *war story* is not.

**Required checks:** this repo is markdown + JSON. A `lint` job that validates every
`plugin.json`/`marketplace.json` against Task 1's confirmed schema and every `SKILL.md` for
required frontmatter is the gate worth having. Do not require a check that does not exist yet —
same rule as everywhere else here.

Tag **`v0.1.0`**.

*Acceptance:* repo exists, ruleset verified via `GET /repos/glunk-works/claude-workbench/rules/branches/main`,
`v0.1.0` tagged, plugin installs cleanly into a scratch directory and `/resume` is *listed* (it
will not run correctly yet — no schema consumers).

### Task 3 — Write the `.ai/project.yml` schema, then generalize against it

`reference/project-schema.md` defines the contract and carries a worked example. Draft shape:

```yaml
repo: glunk-works/bounty-infra
pr_base: main
roadmap: docs/hardening_roadmap.md
sprints_dir: sprints
decision_prefix: BI-D
threat_model: docs/hardening_roadmap.md        # security-critic's ground truth
load_bearing_docs:                             # docs-consistency's audit set
  - CLAUDE.md
  - docs/hardening_roadmap.md
  - .ai/next-steps.md
  - sprints/**/sprint_plan.md

gates:
  green:
    - { cwd: src,   run: hatch run lint:check }
    - { cwd: src,   run: hatch run test:run }
    - { cwd: infra, run: tofu fmt -check -recursive }
    - { cwd: infra, run: "tofu init -backend=false && tofu validate" }

ruleset:
  name: protected-integration-branches
  rule_types: [deletion, non_fast_forward, pull_request, required_status_checks]
  required_checks: [lint, test, tofu-validate, tofu-plan,
                    dependency-audit, sbom, secrets-scan, zizmor]

review:
  ci_gate: null     # loop-orchestrator will set:
                    #   check: architect-review
                    #   header: "**Opus/Architect HITL review (automated)**"
                    #   attestation: "*Fresh-session review: this session did not author the diff.*"

agents:
  enabled: [architect, coder, security-critic, docs-consistency]
models: { architect: opus, coder: sonnet }
```

Then rewrite each skill and agent against it. The full coupling inventory, from grepping the
source:

| File | Coupling to remove | Schema key |
|---|---|---|
| `resume` | 4 rule types + 8 check names inline (L55); `docs/migration_roadmap.md` (L36); the frozen review header (L100) | `ruleset.*`, `roadmap`, `review.ci_gate` |
| `pr-checks` | check names in 8 places; the double-`architect-review`-check-run STALE-RED heuristic | `ruleset.required_checks`, `review.ci_gate.check` |
| `ship` | ruleset name (L18); `loop-orchestrator/*` label namespace (L59); review exemption (L54, L62) | `ruleset.name`, `repo`, `review.ci_gate` |
| `critic-gate` | `hatch run lint && format && test` (L21) | `gates.green` |
| `handoff` | `pointers.roadmap` hardcoded (L34); review-exemption prompt (L60) | `roadmap`, `review.ci_gate` |
| `archive-sprint` | roadmap path (L16) | `roadmap`, `sprints_dir` |
| `retro` | **none** | ships verbatim |
| `architect` | check list (L42); module boundaries; the not-the-CI-gate note (L67) | `ruleset.required_checks`, `review.ci_gate`; boundaries read from local `CLAUDE.md` |
| `security-critic` | loop-orchestrator's threat model by name | `threat_model` |
| `docs-consistency` | the doc set to audit (L9); check list (L36) | `load_bearing_docs`, `ruleset.required_checks` |
| `coder` | `hatch run …` (L26); conventions path (L19) | `gates.green`; plugin `reference/conventions.md` |

**`review.ci_gate: null` is the load-bearing test of the whole design.** bounty-infra has no
`architect-review` check, so every skill must take the no-gate branch cleanly — no dangling
instruction to post a review nobody requires, and `/ship` must not claim exemption from a gate
that does not exist. If that branch is awkward to write, the schema is wrong, not the repo.

**The frozen wire strings stay byte-exact.** `header` and `attestation` move *into* the schema
precisely so they are pasted from data rather than retyped from memory — the failure mode
loop-orchestrator's own docs describe (a paraphrase that reads identically to a human and fails
`contains()` four seconds after posting). Carry the "paste, never paraphrase" warning into
`project-schema.md`, next to the keys.

Tag **`v0.2.0`**.

*Acceptance:* `grep -rE 'hatch run|migration_roadmap|architect-review|loop-orchestrator|Seuss27'`
over `plugins/way-of-working/skills/` and `agents/` returns **zero** hits outside
`project-schema.md`'s example block. That grep is the gate; make it a CI job so the rule cannot
rot.

### Task 4 — Adopt in bounty-infra

Three files:

1. **`.ai/project.yml`** as above, values verified against reality — the 8 required checks
   confirmed against the live ruleset, not copied from this plan.
2. **`.claude/settings.json`** — `extraKnownMarketplaces` pointing at `claude-workbench` **pinned
   to the `v0.2.0` tag**, `enabledPlugins`, plus the deny-list (`gh pr merge`, `git push --force*`)
   ported from loop-orchestrator's. Pinning to a tag rather than a branch is the same rule this
   repo already enforces on GitHub Actions: a mutable ref on something that shapes agent behavior
   is a credential-handoff to whoever moves it. Bumping the tag becomes a reviewed one-line PR.
3. **`CLAUDE.md`, slimmed.** Delete § *Conventions: shared source + local extension* (the
   `raw.githubusercontent` URL — the plugin ships it) and the model-routing / merge-bar prose the
   plugin now owns. **Keep** "What this is", the BI-D5 warning, § *Local: OpenTofu*, § *Local:
   GitHub Actions security*, § *Local: scanner*, § *what must not be committed*, and Pointers.
   Add one line naming the plugin and `.ai/project.yml`.

   Target: **10.4 KB → ~5 KB always-on.** The saving is real but secondary — the point is that
   what remains is all *local truth*, so the file stops changing when the method changes, which
   is what keeps it prompt-cached.

*Acceptance:* a fresh session in this repo lists all 7 skills and can spawn the 4 agents; `/resume`
reads this repo's cursor and reports the **8**-check ruleset (not loop-orchestrator's 8 — the
names differ, which is the point); the `raw.githubusercontent` URL appears nowhere in the repo.

### Task 5 — Run a real sprint through it, and fix what breaks

**This is the acceptance test for Tasks 1–4, and it is not optional.** Pick the next real piece
of work here (the outstanding S1 operator action, or an SG gate) and drive it end to end:
`/resume` → work → `/critic-gate` → `/handoff` → fresh session → `/ship`. Log every place a skill
assumed something untrue about this repo.

Each finding resolves **one** of two ways, and the choice is the sprint's real output:
- **a new schema key** (upstream fix, everyone benefits), or
- **the skill was never portable** and moves back to being repo-local (WB-D4 was wrong about it).

"Override it locally here" is **not** a third option — see the DRY rule at the top.

*Acceptance:* the full loop completes, and every finding is dispositioned as key-or-not-portable
with the reasoning recorded. A clean run with zero findings should be treated as suspicious, not
as success — it more likely means the exercise was too small to exercise the seams.

### Task 6 — Close the third-copy hole

Add a CI job **in loop-orchestrator** that diffs
`src/loop_orchestrator/tools/scaffold/templates/CLAUDE.md` against `claude-workbench`'s
`reference/conventions.md` at the pinned tag, and fails loudly on drift. That template ships
inside the wheel and is read at runtime by `writer.py`, so it must remain a real file — the guard
makes it a *checked* copy instead of a silent fork.

**This task lands in loop-orchestrator, not here**, so it rides that repo's adoption PR rather
than this sprint's. It is listed here because SW is what creates the obligation, and an obligation
recorded only in a PR description is one that gets skipped.

*Acceptance:* the job exists and has gone red once on a deliberate one-character drift, then green
on revert. A guard never observed failing is not a guard.

---

## Session plan — clear points, models, and kickoff prompts

**This section is scaffolding for its own obsolescence.** SW is the sprint that builds `/resume`
and `/handoff`; until it lands, this repo has neither, so the session discipline they automate has
to be run by hand. Once Task 4 completes, `/handoff` writes the cursor and `/resume` reads it, and
everything below collapses into two slash commands. Delete it then.

**Two rules that hold for every session:**

1. **`/clear` between every session below.** `/model` alone does **not** clear context — a session
   that switches model still holds every assumption the previous one made, so it proofreads its
   own reasoning instead of re-deriving it. Each row is a fresh window.
2. **End every session by updating `.ai/next-steps.md`** — what was done, what's next, which model.
   That file is the only cursor SW has until `/handoff` exists, and a session that ends without
   writing it strands the next one.

| # | Task | Model | Ends when |
|---|---|---|---|
| 1 | T1 verify plugin schema | **Sonnet** | the confirmed schema + its source is written down |
| 2 | T2 stand up `claude-workbench` | **Sonnet** | repo + ruleset verified, `v0.1.0` tagged |
| 3 | T3a schema + the 7 skills | **Opus** | `project-schema.md` + all 7 skills generalized |
| 4 | T3b the 4 agents | **Opus** | agents generalized, grep gate green, `v0.2.0` tagged |
| 5 | T4 adopt here | **Opus** | 3 files committed, fresh session lists all 7 skills |
| 6 | T5 drive a real sprint | **Sonnet** | the loop completes; findings logged, not yet judged |
| 7 | T5 disposition findings | **Opus** | every finding is key-or-not-portable, with reasoning |

**Why T3 splits across two sessions.** 7 skills + 4 agents is ~55 KB of source to read and rewrite;
one session accumulates the whole thing and gets slower and less careful as it goes. The split is
the same token-hygiene argument this sprint exists to systematize — it just has to be manual this
once. **Why session 7 is separate from 6:** the session that hit a friction point is the worst one
to judge whether it is a schema gap or a portability limit, because it already has a fix in mind.
Fresh context is the point, exactly as in the review protocol being extracted.

### Session 1 — T1, verify the plugin schema (Sonnet)

```
Read .ai/next-steps.md, then sprints/SW_way_of_working/sprint_plan.md.

Do SW Task 1 only. Verify, against current Claude Code documentation:
  - marketplace.json and plugin.json field names + required keys
  - the plugin subdirectory names (skills/, agents/, hooks/)
  - the hooks.json shape, and whether ${CLAUDE_PLUGIN_ROOT} is the correct
    interpolation for a hook script path
  - the settings keys extraKnownMarketplaces / enabledPlugins, including
    whether the plugin reference is name@marketplace

Report the confirmed schema with its source. Create no repo, write no JSON.

If anything differs from what the sprint plan assumes: STOP and say so.
The plan gets amended by an Opus session, not worked around here.
```

### Session 2 — T2, stand up `claude-workbench` (Sonnet)

```
Read .ai/next-steps.md and sprints/SW_way_of_working/sprint_plan.md Task 2,
plus session 1's confirmed schema recorded in the cursor.

Create glunk-works/claude-workbench per Task 2: public repo, the
protected-integration-branches ruleset mirroring bounty-infra's field-for-field,
the plugin skeleton, docs/decisions.md seeded with WB-D1..D4.

Move conventions.md in VERBATIM from loop-orchestrator's
.ai/context/conventions.md (byte-identical -- Task 6's drift guard depends on the
first diff being empty). Port workflow.md with its loop-orchestrator-specific
war stories replaced by schema references.

Verify the ruleset via the rules/branches/main API, then tag v0.1.0.
Open a PR; do not merge.
```

### Session 3 — T3a, the schema and the 7 skills (Opus)

```
Read .ai/next-steps.md and sprints/SW_way_of_working/sprint_plan.md Task 3.

Write reference/project-schema.md, then generalize the 7 skills against it
using the coupling inventory in Task 3's table. Every literal removed becomes
a schema key.

Hold two things throughout:
  - review.ci_gate: null must be a CLEAN path through every skill -- no dangling
    instruction to post a review nobody requires. If that branch is awkward, the
    schema is wrong, not bounty-infra.
  - the frozen header/attestation strings move into the schema AS DATA so they
    are pasted, never retyped. Carry the paste-never-paraphrase warning into
    project-schema.md next to the keys.

Skills only this session. Agents are session 4.
```

### Session 4 — T3b, the 4 agents (Opus)

```
Read .ai/next-steps.md, sprints/SW_way_of_working/sprint_plan.md Task 3, and
the project-schema.md written in session 3.

Generalize architect, coder, security-critic, docs-consistency against the
schema. security-critic reads `threat_model`; docs-consistency reads
`load_bearing_docs`; both drop their hardcoded check lists.

Then add the acceptance gate as a CI job in claude-workbench:
  grep -rE 'hatch run|migration_roadmap|architect-review|loop-orchestrator|Seuss27'
  over skills/ and agents/ must return ZERO hits outside project-schema.md's
  example block.

Confirm it goes red on a deliberate violation before trusting it green.
Tag v0.2.0. Open a PR; do not merge.
```

### Session 5 — T4, adopt in bounty-infra (Opus)

```
Read .ai/next-steps.md and sprints/SW_way_of_working/sprint_plan.md Task 4.

Land the three files: .ai/project.yml (values verified against the LIVE ruleset,
not copied from the sprint plan), .claude/settings.json (marketplace pinned to
the v0.2.0 TAG, enabledPlugins, the deny-list), and the slimmed CLAUDE.md.

For CLAUDE.md: delete the conventions URL section and the model-routing/merge-bar
prose the plugin now owns. Keep "What this is", the BI-D5 warning, all three
Local: sections, what-must-not-be-committed, and Pointers. Judge each remaining
paragraph by one question -- is this local truth, or is it method? Method goes.

Then verify in a FRESH session that all 7 skills list and /resume reads this
repo's cursor and reports the 8-check ruleset. Open a PR; do not merge.
```

### Session 6 — T5, drive a real sprint through it (Sonnet)

```
Read .ai/next-steps.md. The plugin is live in this repo now.

Pick the next real piece of work (the outstanding S1 operator action, or an SG
gate) and drive it end to end using the plugin:
  /resume -> work -> /critic-gate -> /handoff -> fresh session -> /ship

Log EVERY place a skill assumed something untrue about this repo -- verbatim,
with the skill and the line. Do not fix any of them and do not override a skill
locally; session 7 dispositions them.

A clean run with zero findings is suspicious, not successful -- it means the
exercise was too small to exercise the seams. Say so if that happens.
```

### Session 7 — T5, disposition the findings (Opus)

```
Read .ai/next-steps.md and session 6's findings log.

Disposition each finding exactly one of two ways:
  - a NEW SCHEMA KEY (upstream fix in claude-workbench, everyone benefits), or
  - NOT PORTABLE -- the skill moves back to repo-local, and WB-D4 was wrong
    about it. Say what WB-D4 got wrong.

"Override it locally in bounty-infra" is not a third option -- an override
shadows the whole skill and silently stops receiving upstream fixes (BI-D11).

Record the reasoning per finding, land the schema changes as a claude-workbench
PR, and update .ai/next-steps.md to close SW and point at loop-orchestrator's
adoption sprint. #19 closes here.
```

## Risks

- **The bootstrap trap.** If a generalization breaks `/resume`, the tool used to recover is the
  broken one. This is precisely why loop-orchestrator keeps working local copies for the whole of
  SW (BI-D13). **Do not close the duplication window early** — not until Task 5 has actually run
  clean.
- **Plugin skills cannot be partially overridden.** A repo-local `.claude/skills/resume/` shadows
  the plugin's *entirely*; there is no merge. So a repo that "just needs one tweak" silently forks
  the whole skill and stops receiving upstream fixes. State this in `project-schema.md` as a rule,
  not a footnote.
- **A schema that grows a key per repo has failed.** If adopting repo N+1 needs N+1 new keys, the
  boundary is in the wrong place and the honest answer is a smaller plugin. Watch this at
  loop-orchestrator adoption: it should need `review.ci_gate` populated and little else.
- **Tag-pinning means updates are opt-in, and opt-in means never.** Bumping is a one-line PR per
  repo, which is cheap enough to skip indefinitely. Mitigation is social, not technical: bump as
  part of `/archive-sprint`, so it rides a ritual that already happens.
- **Verified-not-assumed applies to the plugin surface itself.** Task 1 exists because every
  other component in this system that was modeled from memory — tag objects, H1 endpoints,
  gitleaks-action's redaction, zizmor-action's exit code — was wrong in a way that cost a CI run
  or worse.

## Follow-on (not this sprint)

- **loop-orchestrator adoption (Phase 4).** Delete its 7 local skills + 4 shared agents, add
  `project.yml` + settings, keep `mutation-triage`/`live-verify` local, land Task 6's drift guard.
  Worth folding in: its `CLAUDE.md` is **30 KB always-on**, ~20 KB of which is *Enforced module
  boundaries* — that belongs in `.ai/context/boundaries.md`, loaded on demand. It is the same
  lean-routing principle that file's own header states and does not follow. Planned **in that
  repo**, after Task 5.
- **`global-bootstrap` / `scope-core` adoption**, once the schema has survived two repos.
- **Re-point BI-D3's interim URL everywhere it survives** — README, any sprint plan quoting it.
