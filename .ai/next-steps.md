# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Devcontainer (`DC`) — built, PR open, `awaiting_review`.** An owner-prioritised tooling
task, inserted ahead of SE. [PR #54](https://github.com/glunk-works/bounty-infra/pull/54)
needs the owner's review + merge.

## Just done

- **DC build session (Sonnet/Coder), commit `c3ee243`.** Delivered `.devcontainer/Dockerfile` +
  `devcontainer.json` (+ CLI-generated `devcontainer-lock.json`, `.devcontainer/README.md`,
  root `.gitattributes`) per the approved plan
  ([sprints/DC_devcontainer/sprint_plan.md](../sprints/DC_devcontainer/sprint_plan.md)).
  Every non-hatch-provisioned tool (OpenTofu 1.12.5, tflint v0.64.0, gitleaks 8.30.1,
  zizmor 1.28.0, yq 4.53.3, hatch 1.17.1) is version+SHA256-pinned in the Dockerfile.
- **Verified end-to-end, not just built.** Ran `devcontainer build` (Dockerfile + the
  `python:1`/`github-cli:1` features) and executed every plan Task 3 acceptance command
  inside the resulting image against this repo's real `src/` and `infra/` — all green, both
  in-container and on the host. `.gitattributes` included after confirming
  `git add --renormalize .` produces zero churn.
- **`/critic-gate` ran `security-critic` + `docs-consistency`.** No blocking findings; fixed
  what they raised — three Dockerfile comments overstated CI parity for gitleaks/zizmor/
  OpenTofu (CI pins only those tools' *actions*, not the binaries; only tflint's claim was
  actually backed), `hatch` was unpinned, a staging-consistency nit on `yq`, the zizmor
  no-upstream-checksum-manifest caveat needed to live at its `RUN` block not just the file
  header, and the `bookworm` vs. plan's `debian-bookworm` base-image-tag divergence needed
  recording (the latter isn't a valid published tag).
- **PR opened:** [#54](https://github.com/glunk-works/bounty-infra/pull/54), `docs/dc-plan` →
  `main`. Not merged.

## Next

- **Check PR #54's merge status.** If still open, report and wait — do not merge it.
- **Once merged:** run `/archive-sprint` to close DC, then open the SE planning cursor —
  write `sprints/SE_egress_migration/sprint_plan.md` per `docs/hardening_roadmap.md`'s BI-D5
  (scan egress leaves AWS for per-scan ephemeral Vultr VMs; AWS keeps the control plane).
  Architect/Opus.
- **HITL Gate: OPEN.** PR #54 needs the owner's review + merge. Nothing downstream (SE
  planning) should start until it closes.

## Queued behind the devcontainer

- **SE — Egress migration (BI-D5)** — the next *roadmap* sprint (retire ECS/VPC/ECR; per-scan
  Vultr VM; re-point `run-scan.yml`). SE before S2. Plan unwritten.
- **loop-orchestrator adoption (Phase 4)** — the plugin's second adoption, planned *in that
  repo*.

## Still-open operator gates (not sprints; a coder cannot do these)

- **S1: RoE documents don't exist yet.** Fail-closed scanner refuses until
  `s3://<findings-bucket>/roe/<program>/scope.json` exists per engagement (BI-D8/D9).
- **S1: UA contact URL** — confirm `https://hackerone.com/seuss` resolves (a 404 is worse than none).

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model (sprint sequence; BI-D1..D13).
- `sprints/DC_devcontainer/sprint_plan.md` — the approved DC plan (task breakdown + acceptance test).
