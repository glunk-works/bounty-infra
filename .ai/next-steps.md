# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plan, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**S0 — Governance & CI/CD hardening: T1–T3 done; START T4.** Next model
**Sonnet/coder** — T4 is already specified in
`sprints/S0_governance_hardening/sprint_plan.md`, so this is executing a written spec, not
designing one.

| Task | State |
|---|---|
| **T1** branch protection + method scaffold | ✅ ruleset · scaffold (#24) · required-checks list (landed with T3, PR #27) |
| **T2** gated OpenTofu deploy (#9) | ✅ **verified end to end** — plan no-op on PR; apply approved → applied (#25, #26) |
| **T3** non-bypassable CI (#8) | ✅ **done** (PR #27) — all 5 parts (a–e); see below |
| **T4** `run-scan.yml` injection fix (#6) + drop unused token (#10) | ⬜ not started — **next** |

## Just done (2026-07-21) — T3, non-bypassable CI (#8), PR #27

- **(a)** `ci.yml` dropped its `paths:` filter — runs on every PR, no deadlock risk.
- **(b)** Split the old combined `validate` job into `lint` + `test` job ids, no
  `name:` overrides anywhere in `ci.yml` — job id is now exactly the required-check
  context.
- **(c)** New credential-free `tofu-validate` job: `fmt -check -recursive`,
  `init -backend=false && validate`, pinned `tflint` (`terraform-linters/setup-tflint@v6`,
  tflint `v0.64.0` — verified both tags exist via the GitHub API before pinning, since a
  wrong guess would have broken CI on the first run).
- **(d)** `build-image.yml` no longer pushes `:latest`. It pushes only
  `:${{ github.sha }}` and calls `aws ecs register-task-definition` directly to roll that
  image into a new task-definition revision — bypassing Tofu **on purpose** for just this
  field. `infra/main.tf`'s `aws_ecs_task_definition.scanner_task` now carries
  `lifecycle.ignore_changes = [container_definitions]` so Tofu stops reverting CI's
  rollouts on the next unrelated apply. New `variable "image_tag"` (default `"latest"`) is
  bootstrap-only — confirmed via a real `tofu-plan` run that this produces **zero diff**
  against current state (the default matches what's already deployed, so nothing broke).
  **This is a real architectural call, not literally spelled out in the sprint plan** — CI
  now owns image rollouts for this one field; BI-D2's plan+approval gate still covers
  everything else in that resource. User confirmed this design before it was pushed. If
  the OPEN compute-model question (Fargate/Docker vs. Ansible) is ever resolved, revisit
  this split.
- **(e)** Ported loop-orchestrator's `ruleset-drift.yml` structure, retargeted at this
  repo's 4-check taxonomy (`lint`, `test`, `tofu-validate`, `tofu-plan`) instead of
  loop-orchestrator's 8. Verified via `workflow_dispatch` against the live ruleset —
  passes clean (run 29859578890).
- **Required-status-checks applied to the live ruleset** (the piece T1 deferred): fetched
  loop-orchestrator's live `required_status_checks` parameters first
  (`strict_required_status_checks_policy: false`, `do_not_enforce_on_create: false`) and
  mirrored the shape exactly rather than guessing. Applied only after all 4 checks had
  already run green on PR #27 — never require a check that hasn't reported yet.
  `GET /repos/glunk-works/bounty-infra/rules/branches/main` now shows all 4 rule types
  (`deletion`, `non_fast_forward`, `pull_request`, `required_status_checks`) and all 4
  contexts.
- **Recovered a second stranded-commit incident** (same shape as the T2 one below, #26):
  `docs/s0-t2-verified-credential-model`'s final commit (this section's "point the cursor
  at T3" update) was pushed ~2 minutes *after* PR #26 squash-merged, so `main` never got
  it — this file's own "Now" section still read "START T3" as of a fresh `main` pull.
  Cherry-picked it onto the T3 branch before writing this update. **The gotcha below about
  checking `git log origin/<branch> --not main` before trusting a branch is done applies
  to reading this very file, not just deleting branches** — always diff against `origin/main`
  before trusting a cursor file's "Now" section.

## Previously done (2026-07-21)

- **Ruleset `protected-integration-branches`** (id `19438326`) active on `refs/heads/main`:
  `pull_request` + `deletion` + `non_fast_forward`, `bypass_actors: []`,
  `required_approving_review_count: 0`. Matches loop-orchestrator's field-for-field.
- **`docs/hardening_roadmap.md`** — reference of record (#20, #21, #22): posture,
  BI-D1..BI-D4, sprint sequence, public-repo rules, OPEN compute-model question.
- **Deleted `oidc-debug.yml` + `test_oidc.yml`** (#23) — an unpinned third-party action
  holding `id-token: write`, and an `aws sts get-caller-identity` echo into a
  world-readable public-repo log. One-off bring-up aids on no delivery path; **neither was
  covered by any issue or sprint**, so "covered by a finding" ≠ "reviewed."
- **T1 scaffold** (#24) — `CLAUDE.md` (routing layer + bounty-infra local conventions) and
  this cursor.
- **T2 gated deploy** (this PR) — `plan-infra.yml` (job `tofu-plan`, every PR, summary-only
  output) + `deploy-infra.yml` (job `apply`, `environment: production`). The `production`
  Environment is live: required reviewer `Seuss27`, `prevent_self_review: false`,
  deployments restricted to `main`. **Five deviations** from the plan as written are recorded
  in the sprint plan's T2 entry — read them before touching either workflow.
  **Both paths verified live 2026-07-21:** plan gave `tofu plan exit code: 0` (no-op against
  real state); apply parked for approval, was approved, authenticated, and applied a no-op.

## Credential model for the two infra workflows (verified end-to-end 2026-07-21)

Two OIDC hops, each validating independently: GitHub → Infisical (audience
`https://github.com/glunk-works/bounty-infra`), then Infisical's `AWS_*_ROLE_ARN` → AWS
(audience `sts.amazonaws.com`). **The two hops bind on different things** — that asymmetry
is the whole lesson of T2:

| Path | Infisical identity | Infisical binds on | AWS role | AWS trusts subject |
|---|---|---|---|---|
| plan (PR) | `vars.PLAN_IDENTITY_ID` | subject `:pull_request` | `github-actions-bounty-infra-plan` | `:pull_request` |
| apply (merge/dispatch) | `vars.IDENTITY_ID` | **claims** `repository` + `ref` | `github-actions-bounty-infra` | `:ref:refs/heads/main` **+** `:environment:production` |

**Why the apply identity binds on claims, not subject.** Adding `environment: production`
changed the job's `sub` to `:environment:production`, but that identity is shared with
`build-image.yml` and `run-scan.yml`, which still present `:ref:refs/heads/main` — and
Infisical's **Subject field holds one value** (globs, but no reliable list; a
comma-separated pair was tried and rejected with 403). A glob wide enough for both
(`repo:…:*`) would also match `:pull_request` and hand the apply identity to every PR.
So the binding moved to the claims that are **invariant to the environment**:

- `repository` = `glunk-works/bounty-infra`
- `ref` = `refs/heads/main`

Equivalent, not looser: for the non-environment workflows `sub` encodes exactly
`repository` + `ref`, so the same jobs are admitted plus the environment-gated apply. PR
runs still fail — their `ref` is `refs/pull/N/merge`.

The plan role is read-only, state-prefix-limited, and carries an explicit `Deny` on the
findings bucket. AWS side is code in `glunk-works/global-bootstrap` (`plan_roles.tf`);
**the Infisical side has no IaC** and was configured by hand — it is the one part of this
model that cannot be reviewed in a diff.

**Never merge the two identities.** Widening the apply identity to accept `:pull_request`
would make merely *opening* a PR grant apply-capable credentials with no approval —
workflow changes in a PR take effect for `pull_request` runs — re-opening #9 sideways.

## Next — T4, `run-scan.yml` injection fix (#6) + drop unused token (#10)

Rewrite the *Trigger Scan Task* step so no `${{ github.event.inputs.* }}` is interpolated
inline into a `run:` shell block: pass the four dispatch inputs via `env:`, build the ECS
`--overrides` JSON with `jq -n --arg`, add a strict hostname regex on `target_domain`, drop
`GITHUB_TOKEN`/`issues: write` (unused — the scanner only writes to S3). **Verification is
behavioral, not structural** — dispatch a `'`-containing `target_domain` and prove it's
rejected, don't just eyeball the `jq` rewrite. loop-orchestrator's `ruleset-drift.yml` (now
ported here too) is cited in the sprint plan as the in-house reference shape for the
`env:`/`jq` pattern. **T4 blocks loop-orchestrator #18** (its `seed`/`token` inputs need to
ride this safe pattern), so this is the last thing standing between S0 and that cross-repo
unblock.

## Gotchas worth remembering

- **Never require a status check that does not exist yet** — it strands every open PR.
  **Resolved for T3's taxonomy** (`lint`, `test`, `tofu-validate`, `tofu-plan` — all
  required on `main` now), but the principle stands for whatever T4 or a later sprint adds.
- **Required checks match by check-run name = job id.** Do not add a `name:` override to a
  gated job — `ci.yml`'s jobs are bare (`lint`, `test`, `tofu-validate`) since T3; keep it
  that way.
- **`ruleset-drift.yml` must NOT be a required check and must NOT be a job in `ci.yml`** —
  a required check is required only because the ruleset says so, so making the drift guard
  required would un-require it the instant the ruleset it watches is deleted, silently, on
  the exact failure it exists to catch (loop-orchestrator FD2).
- **`build-image.yml` was the missing half of #8 — fixed in T3(d).** It used to push
  `:latest` to a `MUTABLE` ECR repo with no CI dependency, so merging any `src/**` change
  silently replaced production Fargate code. Now sha-pinned + CI-gated (see T3 above); the
  ECR repo itself is still `MUTABLE` (left alone — only the task-definition image
  reference and the tag scheme changed).
- **#6 verification is behavioral, not structural** — dispatch a `'`-containing
  `target_domain` and prove it is rejected, don't just eyeball the `jq` rewrite.
- **#6 blocks loop-orchestrator #18.** Its `seed`/`token` inputs must ride T4's safe
  `env:` + `jq --arg` pattern, so S0-T4 ships before #18.
- **`.ai/state.json` is git-ignored** — this file (`next-steps.md`) is what travels.
- **Never `paths:`-filter a workflow that hosts a required check** (T2 deviation (i)) — the
  filter and the requirement deadlock. Path awareness belongs *inside* the job, as a
  step-level `if:`, so the job always reports a conclusion.
- **Never upload `tfplan.bin` or a plan/apply body as an artifact or PR comment.** It
  embeds the account ID, bucket names, subnet/SG IDs and ARNs, and on a public repo
  artifacts are as world-readable as comments (BI-D4). Publish addresses + counts only.
- **Adding an `environment:` to a job CHANGES its OIDC subject.** GitHub's subject filters
  are ordered: an Environment wins over `pull_request`, which wins over the branch ref. So
  a job that gains `environment: production` stops presenting `:ref:refs/heads/main` and
  starts presenting `:environment:production` — invalidating its credentials at **both**
  hops. Changing a job's trigger or environment is a change to its **identity**. Where the
  verifier takes a list (the AWS trust condition) **append**, never replace, because
  sibling workflows on the same role still use the old subject; where it takes one value
  (Infisical's Subject) **bind on `repository` + `ref` claims instead** — they don't move
  when an environment is added. Never paper over it with a `repo:…:*` glob: that matches
  `:pull_request` too.
- **`deploy-infra.yml` self-triggers.** Its `paths:` filter includes its own file, so a PR
  that edits the workflow queues an apply on merge — even with no `infra/**` change. Useful
  (workflow edits get exercised immediately) but easy to misjudge: I predicted merging T2
  would not trigger an apply, and it did.
- **The `production` Environment is what makes `deploy-infra.yml` safe, not the YAML.**
  If `environment: production` ever names an environment that does not exist, GitHub
  auto-creates it **unprotected** and the apply runs unattended — silently re-opening #9.
- **Pushing to a branch after its PR merges silently drops the work — this has now
  happened three times in a row** (#25→#26, then again #26→#27, then again on #27's own
  branch, recovered by branching fresh from `main` rather than a third cherry-pick chain).
  The reviewer can merge the moment required checks go green; a cursor-file update queued
  right after tends to lose the race. **Before pushing a docs-only follow-up to an
  already-open PR's branch, check `gh pr view <N> --json state` first** — if it says
  `MERGED`, branch fresh from `main` instead of pushing more commits to the dead branch.
  And before trusting this file's own "Now" section, or deleting any merged branch, run
  `git log origin/<branch> --not origin/main` to make sure nothing on it is still stranded.
- Never commit to `main`, never merge your own PR, never force-push a pushed branch.

## OPEN — not scheduled anywhere

- **The four unadopted shared gates.** loop-orchestrator requires `secrets-scan`,
  `dependency-audit`, `sbom`, `pr-title`; this repo has none, and no sprint schedules them.
  `secrets-scan` has the strongest same-sprint argument given the repo is public.
- **The compute-model decision** (Fargate/Docker as-built vs the Ansible-provisioned VM
  model the docs describe). Needs its own architecture pass — it moves the IAM model and
  the S3 output path all three sprints assume.
- **The central conventions repo (BI-D3).** `CLAUDE.md` points at loop-orchestrator's
  `conventions.md` as the interim source; re-point once the central repo exists.
- **Infisical has no IaC.** Both machine identities are hand-configured and invisible to
  code review, unlike the AWS half (`global-bootstrap` Terraform). Lose or alter that config
  and nothing detects it — the failure surfaces as a 403 at deploy time. Infisical does ship
  a Terraform provider if this is ever worth closing.
- **`glunk-works/global-bootstrap`: the `ecs:RunTask` scoping is inert.** `RunTask` is
  granted both in the ARN-scoped statement and in the broad `Resource = "*"` one, so the
  scoping restricts nothing. Removing it from the broad list makes it real (noted on
  global-bootstrap#2, never filed as an issue).

## Pointers

- [`docs/hardening_roadmap.md`](../docs/hardening_roadmap.md) — reference of record.
- [`sprints/S0_governance_hardening/sprint_plan.md`](../sprints/S0_governance_hardening/sprint_plan.md)
  — the S0 plan (T1–T4, acceptance criteria, risks).
- Issues **#6–#14** (2026-07-19 review), **#18** (recon dispatch contract, cross-repo),
  **#19** (adopt the working method — this sprint).
- Draft advisories `GHSA-59j8-c4rc-2jf4` (#6), `GHSA-pf9q-vx7g-f8gr` (#7),
  `GHSA-p3hr-h7cq-xp5m` (#13) — publish as each sprint closes.
