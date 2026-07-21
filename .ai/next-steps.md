# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plan, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**S0 — Governance & CI/CD hardening: T2 in flight.** T1 is done bar the required-checks
list; this PR lands T2. Next model **Sonnet/coder** for T3–T4 (each is an already-specified
task in `sprints/S0_governance_hardening/sprint_plan.md`).

| Task | State |
|---|---|
| **T1** branch protection + method scaffold | ruleset ✅ · scaffold ✅ (#24) · required-checks list ⬜ (deferred to end of S0) |
| **T2** gated OpenTofu deploy (#9) | ✅ this PR — verify the live `tofu-plan` run on it before merging |
| **T3** non-bypassable CI (#8) | ⬜ not started |
| **T4** `run-scan.yml` injection fix (#6) + drop unused token (#10) | ⬜ not started |

## Just done (2026-07-21)

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
  deployments restricted to `main`. Four deviations from the plan as written are recorded
  in the sprint plan's T2 entry — read them before touching either workflow.

## Next — T3, non-bypassable CI (#8)

Five parts, all specified in the sprint plan: (a) drop `ci.yml`'s `paths:` filters,
(b) rename jobs to `lint`/`test` and drop the `name:` overrides, (c) add a credential-free
`tofu-validate` job (`fmt -check`, `init -backend=false && validate`, pinned `tflint`),
(d) gate `build-image.yml` on CI green and deploy a sha-pinned image instead of `:latest`,
(e) port loop-orchestrator's `ruleset-drift.yml`. **(d) is the one that matters most** —
without it, T2's infra gate is a false gate.

## Gotchas worth remembering

- **Never require a status check that does not exist yet** — it strands every open PR.
  The required-checks list is applied at the **end** of S0, after T2/T3's jobs have run
  once, and must match the T3 taxonomy (`lint`, `test`, `tofu-validate`, `tofu-plan`).
- **Required checks match by check-run name = job id.** Do not add a `name:` override to a
  gated job; `ci.yml` currently has `name: "Lint & Test"` / `"Hatch Build & Validate"`,
  which T3 removes.
- **`ruleset-drift.yml` (T3e) must NOT be a required check and must NOT be a job in
  `ci.yml`** — a required check is required only because the ruleset says so, so making
  the drift guard required would un-require it the instant the ruleset it watches is
  deleted, silently, on the exact failure it exists to catch (loop-orchestrator FD2).
- **`build-image.yml` is the missing half of #8.** It pushes `:latest` to a `MUTABLE` ECR
  repo and the task definition runs `…:latest`, so merging any `src/**` change silently
  replaces production Fargate code with no CI, no plan, no approval. Gating the infra apply
  (T2) while leaving this open would be a **false gate**.
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
- **The `production` Environment is what makes `deploy-infra.yml` safe, not the YAML.**
  If `environment: production` ever names an environment that does not exist, GitHub
  auto-creates it **unprotected** and the apply runs unattended — silently re-opening #9.
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

## Pointers

- [`docs/hardening_roadmap.md`](../docs/hardening_roadmap.md) — reference of record.
- [`sprints/S0_governance_hardening/sprint_plan.md`](../sprints/S0_governance_hardening/sprint_plan.md)
  — the S0 plan (T1–T4, acceptance criteria, risks).
- Issues **#6–#14** (2026-07-19 review), **#18** (recon dispatch contract, cross-repo),
  **#19** (adopt the working method — this sprint).
- Draft advisories `GHSA-59j8-c4rc-2jf4` (#6), `GHSA-pf9q-vx7g-f8gr` (#7),
  `GHSA-p3hr-h7cq-xp5m` (#13) — publish as each sprint closes.
