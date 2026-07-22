# Task 5, session 6 — findings log

Produced while driving a real piece of outstanding work (the S1 UA eyeball check +
authoring `docs/roe_operator_runbook.md`) end to end through the plugin loop:
`/way-of-working:resume` → work → `/way-of-working:critic-gate` → `/way-of-working:handoff`.

Per the sprint plan (`sprint_plan.md`, Session 6): **not fixed here, not overridden
locally** — session 7 (Opus) dispositions each as a new schema key or "never portable."
This run was **not** a clean pass — five findings, all real, all verbatim.

## F1 — `/way-of-working:resume` step 4 hardcodes loop-orchestrator's own required-check list

**Skill:** `way-of-working:resume`, § step 4 (ruleset check).

**Verbatim:** "Confirm the response includes all four rule types (`deletion`,
`non_fast_forward`, `pull_request`, `required_status_checks`) and that the
`required_status_checks` rule's contexts cover all eight: `lint`, `format-check`, `test`,
`secrets-scan`, `dependency-audit`, `sbom`, `pr-title`, `architect-review`."

That eight-item list is loop-orchestrator's own required checks, written as prose, not
sourced from `.ai/project.yml`'s `ruleset.required_checks`. bounty-infra's real list is
`lint`, `test`, `tofu-validate`, `tofu-plan`, `dependency-audit`, `sbom`, `secrets-scan`,
`zizmor` — three names differ (`format-check`/`pr-title`/`architect-review` vs.
`tofu-validate`/`tofu-plan`/`zizmor`). I substituted the schema value by judgment both
times `/way-of-working:resume` ran this session; a literal reading of the step would have
compared against the wrong list and reported bounty-infra's real ruleset as *unhealthy*
(missing `format-check`/`pr-title`/`architect-review`, extra unexpected checks).

## F2 — `/way-of-working:resume` step 1 hardcodes `docs/migration_roadmap.md`

**Skill:** `way-of-working:resume`, § step 1, 4th bullet.

**Verbatim:** "`docs/migration_roadmap.md` — read only the **Status table** + the **NEXT
ACTION** line, not the whole file, unless the next action needs the decisions log."

bounty-infra's roadmap is `docs/hardening_roadmap.md` (`.ai/project.yml`'s `roadmap:` key)
— `docs/migration_roadmap.md` does not exist in this repo. Not parameterized as `{roadmap}`
despite the schema key existing for exactly this purpose.

## F3 — `/way-of-working:resume` step 5 and `/way-of-working:handoff` step 2 hardcode `.ai/context/workflow.md`

**Skills:** `way-of-working:resume` § step 5; `way-of-working:handoff` § step 2 (model
bullet) and § step 6 (Architect Review note).

**Verbatim (resume):** "Architect=Opus for planning/review, Coder=Sonnet for
implementation — see `.ai/context/workflow.md`."
**Verbatim (handoff):** "(Architect=Opus for planning/review, Coder=Sonnet for
implementation — see `.ai/context/workflow.md`)."

bounty-infra has no `.ai/context/` directory at all (confirmed: `.ai/` contains only
`next-steps.md` and `project.yml`). Per `CLAUDE.md`, model-routing/merge-bar content now
lives in the plugin's own `reference/conventions.md`, parameterized by `.ai/project.yml`'s
`models:` key — the skill text still points at the old loop-orchestrator-shaped path
instead of that.

## F4 — `/way-of-working:resume`'s "Load-on-demand" footer hardcodes two more `.ai/context/` files

**Skill:** `way-of-working:resume`, final section.

**Verbatim:** "Only read `.ai/context/modules.md` / `conventions.md` if the next action
actually needs them."

Same root cause as F3 — neither file exists in bounty-infra.

**Root cause common to F1–F4:** per the sprint plan's own Task 3b record, the coupling-check
CI gate greps `skills/`/`agents/` for a fixed list of repo/org name strings (`bounty-infra`,
`loop-orchestrator`, `global-bootstrap`, `scope-core`, `glunk-works`). None of
`docs/migration_roadmap.md`, `.ai/context/workflow.md`, `.ai/context/modules.md`,
`.ai/context/conventions.md`, or the loop-orchestrator required-check names contain any of
those strings — the gate is structurally blind to a hardcoded *path or value* that isn't a
repo name. "Acceptance grep returns zero hits" (Task 3a/3b) is true of what the grep
checks; it is not proof the skills are fully parameterized.

## F5 — `/way-of-working:critic-gate`'s docs-consistency trigger is ambiguous for a new, untracked doc

**Skill:** `way-of-working:critic-gate`, § step 2 table, docs-consistency row.

**Verbatim:** "load-bearing docs / roadmap / CLAUDE.md → propose `docs-consistency`."

This session's diff (`docs/roe_operator_runbook.md`, a new file documenting a real
S3/KMS upload procedure) is not in `.ai/project.yml`'s `load_bearing_docs` set and isn't
the roadmap or `CLAUDE.md`, so per the schema no critic was proposed — technically correct
by the letter of the schema (`load_bearing_docs` is a fixed drift-audit set, not "anything
under `docs/`"), but the table's plain-English phrasing reads broader than that. Not a
hardcoded-value bug like F1–F4; a phrasing/scope question worth an explicit disposition:
should a *new* security-relevant doc get any critic look before merge, or is that
deliberately out of scope for `docs-consistency` (which audits drift in existing docs, not
the arrival of new ones)?

## F6 — `/way-of-working:handoff` step 5's "never commit the cursor sync on a code branch" rule breaks when that branch's own PR is the prerequisite

**Skill:** `way-of-working:handoff`, § step 5.

**Verbatim:** "If the current branch is a code branch (e.g. mid-implementation, or the
just-pushed feature branch), do **not** commit the cursor sync there — switch to `main`
… cut a fresh small branch … and commit `.ai/next-steps.md` there."

`sprint/SW-t4-adopt` (PR #48, open, unmerged) is exactly "the just-pushed feature branch"
this rule targets. But `origin/main` doesn't yet contain PR #48's content (the T4 adoption
narrative this session's cursor update is appended after) — cutting a fresh branch from
`main` right now cannot carry this edit, since the diff's context doesn't exist there yet.
**This repo's own git history already deviated from the literal rule for the same reason**:
`cb6d698` ("sync cursor after Task 4") is a direct child of `45280f7` ("adopt the
way-of-working plugin (T4)"), both on `sprint/SW-t4-adopt`, both absent from
`origin/main` (confirmed via `git log origin/main..HEAD`) — i.e. session 5's own
`/handoff` (or a human) already committed the cursor sync onto the code branch, not a
fresh branch off `main`. Session 6 follows the same precedent for the same reason. The
skill has no stated exception for "the cursor update's own content depends on an unmerged
PR" — Tasks 1/2/3a/3b's cursor syncs all genuinely fit the branch-from-main rule (their
prerequisite PRs had already merged by sync time), so this gap was invisible until a sprint
stacked two sessions on one still-open PR.

## Not a finding — positive confirmations worth recording alongside the failures

- `.ai/project.yml`'s `code_paths` correctly classified this diff as non-code (`docs/` is
  absent from `[src/, infra/, .github/workflows/]`) — `critic-gate`'s `src/`/guard/tests
  rows correctly did not fire.
- A live-spawned `way-of-working:architect` subagent cold-read `.ai/project.yml` and
  reported bounty-infra's own values (`code_paths`, `ruleset.required_checks`), not
  loop-orchestrator's — WB-D5's "agents build their instance list at spawn time" design
  held up under a real spawn, not just in the sprint-plan record.
