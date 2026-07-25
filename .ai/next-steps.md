# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — DONE.** Both phases merged, applied, and live-verified.
No sprint currently in flight; the next session should plan which sprint comes next.

## Just done (this session — SE Phase 2: the AWS Fargate teardown)

- **PR #78**: deleted the AWS Fargate estate from `infra/` (VPC/IGW/subnet/route/RTA/SG,
  ECS cluster/task-def, ECR repo, CloudWatch log group, both Fargate IAM roles + policies),
  dropped the four dead `outputs.tf` entries + `image_tag`, and rewrote
  `README.md`/`CLAUDE.md`/`docs/hardening_roadmap.md` for the Vultr-only reality. Closed
  **#11** (its task role no longer exists; SE-MG2's STS session policy is the replacement).
- **Ran `/critic-gate`** (architect + security-critic + docs-consistency) on that diff
  before merge — the only critic look it got (`review.ci_gate: null`):
  - **architect** caught a real high-severity defect: deleting `required_providers.aws` +
    `provider "aws"` in the same PR that needs to destroy AWS resources still in real
    state would break the destroy (Tofu needs the provider config present to plan/execute
    it). Fixed — kept the provider block, with a comment explaining why; follow-up to
    remove it once state is confirmed clean is **#79**.
  - **docs-consistency** found and fixed 3 stale references (README's workflow display
    name, a present-tense #11 mention, a phantom step name in CLAUDE.md).
  - **security-critic**: clean.
- **PR #78's `tofu-plan` hit a transient GitHub platform error** (0 jobs scheduled, twice)
  — `gh run rerun` resolved it; the real plan then correctly showed destroys-only.
- **The merge-time apply failed for a genuine reason**: `github-actions-bounty-infra`'s
  IAM policy (in `glunk-works/global-bootstrap`) never had
  `ec2:DescribeNetworkInterfaces`/`DeleteNetworkInterface` — nothing had ever *destroyed*
  this VPC/subnet/SG before (only ever created), so the gap was never exercised. Shipped
  **global-bootstrap PR #4** (scoped, `tofu validate`d, GPG-signed) to add the two missing
  actions to the existing `bounty_infra_policy` statement — no new role, no widened trust.
  Operator merged + applied it; the re-run apply then succeeded cleanly (verified via the
  GitHub Actions API).
- **tflint** (part of the required `tofu-validate` check, not in this repo's local green
  gate) failed on `findings_bucket_name`/`kms_key_arn` going unused once their last
  consumer (`aws_iam_policy.s3_write_policy`) was deleted — but both must stay *declared*
  because `plan-infra.yml`/`deploy-infra.yml` still pass them via `-var=`, and this
  OpenTofu version hard-errors on `-var` for an undeclared root variable (verified by a
  local test, not assumed). Fixed with `tflint-ignore` directives + an explaining comment,
  not by removing the variables.

## Next

- **Run `/archive-sprint` for SE** — complete, no open HITL gate, fully committed/applied.
- **Then hold an architect planning pass to pick the next sprint.** Do not assume ordering
  from memory — re-check `sprints/*/sprint_plan.md` and each issue's live state:
  - **S1** (scanner security core) — #7 already closed; **#13** (prompt-injection
    hardening) and **#32** (traffic attribution/rate limiting) still open.
  - **S2** (scanner robustness) — **#12** (pin tools/deps) and **#14** (partial/failed-scan
    detection) still open; #11 no longer belongs to it (closed via SE).
  - **SC** (scope-core extraction) — BI-D6 says this is a *prerequisite* for S1.
  - **SG** (CI gate expansion) — the four substrate-independent gates
    (`dependency-audit`/`sbom`/`secrets-scan`/`zizmor`) are already required per
    `.ai/project.yml`'s ruleset; only the two AWS/infra-dependent gates (IaC security scan,
    container image scan) may remain, and BI-D5's ordering note says those should follow
    SE — which just finished. Confirm what's actually left before scoping it.
- **Recon-coverage gap** (issue #76) — queued, not urgent, S1/S2 scope.
- **Issue #79** — once a fresh `tofu plan` on `main` confirms zero AWS resources remain in
  state, drop `infra/main.tf`'s now-vestigial `provider "aws"` block and `var.aws_region`
  (and the matching workflow `-var=` flag). Small and mechanical; not urgent.

## Still-open operator gates (a coder cannot do these)

- **Reserved IP** — provision only when onboarding a program that mandates
  source-IP registration (MG5): flip `reserved_ip_enabled`, apply, register, dispatch
  with `use_reserved_ip=true`.
- **Proactive abuse-team notification to Vultr** (BI-D5) — not yet done.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; SE's row now reads DONE.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved, now fully-executed SE plan.
- PRs this session: bounty-infra [#78](https://github.com/glunk-works/bounty-infra/pull/78),
  global-bootstrap [#4](https://github.com/glunk-works/global-bootstrap/pull/4).
- Issues: [#79](https://github.com/glunk-works/bounty-infra/issues/79) (provider-block
  cleanup), [#76](https://github.com/glunk-works/bounty-infra/issues/76) (recon coverage).
