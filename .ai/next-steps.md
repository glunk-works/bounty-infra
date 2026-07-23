# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `implementing`.** PR1 merged and applied
([#57](https://github.com/glunk-works/bounty-infra/pull/57)). All three prerequisites for
Task 5 (the live proof) are done — **ready to dispatch.**

## Just done

- **PR1 merged and applied**: Vultr provider + firewall group live in the real account (zero
  standing cost); `build-image.yml` pushes to public GHCR; `run-scan.yml` is the Vultr
  launch/poll/destroy loop. Found and fixed a pre-existing `plan-infra.yml` bug along the way
  (`opentofu/setup-opentofu`'s wrapper swallowed `-detailed-exitcode`'s real code — fixed with
  `tofu_wrapper: false`).
- **`ghcr.io/glunk-works/bounty-scanner` flipped to public** on GitHub.
- **Cross-repo prerequisite landed**: `global-bootstrap`
  [#3](https://github.com/glunk-works/global-bootstrap/pull/3) (the `bounty-scanner-s3-writer`
  role) merged and applied locally; `AWS_SCANNER_WRITER_ROLE_ARN` is in bounty-infra's
  Infisical.
- **RoE placed for the live target**: `s3://seuss-bounty-infra-findings/roe/DIB-VDP/scope.json`
  uploaded by the operator. Content validated in-session against the real `Program` pydantic
  schema and `translate_program_scope` — produces exactly one in-scope pattern
  (`^ztna\.myngc\.com$`), zero dropped entries. **This is a real, operator-confirmed-authorized
  program (DIB-VDP), not the sprint plan's originally-described hermetic operator-owned-domain
  proof** — say so plainly in the next update; a live result against a real program and a
  hermetic operator-owned-domain result are different claims.

## Next

- **HITL Gate: OPEN — dispatch is the operator's call.** Not something a coder auto-starts:
  this fires live scanning traffic at a real, third-party-adjacent target. A coder may prep
  (confirm an `image_tag` exists on GHCR from PR1's build — merge commit `920eb4c` — or
  trigger a fresh `build-image.yml` run) but should not fire the dispatch unattended.
- **Dispatch `run-scan.yml`**: `target_domain=ztna.myngc.com`, `program=DIB-VDP`,
  `use_reserved_ip=false`, `image_tag=<confirmed sha>`. Confirm: a Vultr instance boots, the
  scan runs, findings land in S3 **from the Vultr IP**, the status sentinel drives a clean
  exit, the instance is destroyed. That confirmation **is** the Phase-1 DoD (with the caveat
  above about it being a live-program result, not the originally-scoped hermetic one).

## Queued behind the live proof

- **PR2 (teardown)** — delete the AWS Fargate/VPC/ECR/IAM estate as a destroys-only,
  summarized plan (BI-D2); docs pass; mark SE done; close #11. Only after the Phase-1 proof.
- **S2 — Scanner robustness** — follows SE (#11 is closed here; #14 only partly advanced via
  the status sentinel).
- **loop-orchestrator Phase 4** — planned in that repo.

## Still-open operator gates (a coder cannot do these)

- **Reserved IP** — provision only when onboarding a program that mandates source-IP
  registration (MG5): flip `reserved_ip_enabled`, apply, register, dispatch with
  `use_reserved_ip=true`. The `reserved_ipv4` field's exact semantics (id vs. address) are
  noted in `run-scan.yml` as unverified against a live call — confirm before the first such
  dispatch.
- **Proactive abuse-team notification to Vultr** (BI-D5) — not yet done; should happen before
  or alongside the first live scan, per the sprint plan's operator procedural gates.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; read **BI-D5**.
- `sprints/SE_egress_migration/sprint_plan.md` — the approved plan (MG1–MG5, two-phase task
  breakdown, DoD, operator gates).
