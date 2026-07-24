# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `implementing`.** Task 5 (the live proof) is still
**not met**. Five bootstrap-robustness fixes landed this session, but the scan pipeline
still never completes on a live VM — root cause unknown. SSH debug access now works
end-to-end and is the next diagnostic step.

## Just done (this session — an incident-response chain, not planned work)

- **PR #62**: fixed SE-MG2 role assumption (`sts:TagSession` denied by the trust policy) —
  the original Task 5 blocker from the prior session.
- **PR #63**: unrelated `ruff` 0.16 lint drift (unpinned tool version, #12) fixed to unblock
  CI for #62.
- **PR #64**: `run_recon_pipeline`'s `timeout` now bounds the WHOLE pipeline (one shared
  deadline) instead of being handed unchanged to each of subfinder/httpx/nuclei — the
  pipeline could legitimately run up to 3x `timeout` before this.
- **PR #65**: made the VM's S3 status sentinel unconditional — `scan-vm-userdata.sh.tftpl`
  ran under `set -e` with only `docker run` guarded; any earlier failure (apt-get) died
  silently before ever writing the sentinel.
- **PR #66**: wrapped every VM-bootstrap command in `timeout`, added
  `DEBIAN_FRONTEND=noninteractive` + `NEEDRESTART_MODE=a` (Ubuntu 24.04's `needrestart`
  can prompt interactively on a `docker.io` install with no TTY to answer it).
- **Despite all five fixes**: four live dispatches (1 against the real target
  `ztna.myngc.com`, 3 against sandbox `scanme.nmap.org` — see `roe/SANDBOX-NMAP/scope.json`,
  a trivial single-host target used specifically to avoid repeated live-program traffic
  while debugging) **all failed identically** — full 35-minute poll deadline exhausted,
  zero status sentinel ever written, even against a target with negligible scan surface.
  **The actual root cause is still unknown.**
- Tried live Vultr console access to observe boot directly — **failed to connect**
  (Vultr-side console proxy issue, instance itself showed "running").
- **PR #68**: added `enable_ssh_debug` (`workflow_dispatch` input, default `false`) — opens
  a temporary, IP-scoped SSH ingress rule + injects `OPERATOR_SSH_KEY`, entirely via direct
  Vultr API calls in `run-scan.yml` (no `infra/main.tf` change, no `tofu apply` needed).
  Deliberately opt-in; BI-D5 zero-ingress stays default for every real scan.
- **PR #69, #70, #71**: three real bugs found and fixed getting SSH debug actually working
  — `curl -f` was discarding the Vultr API's error body (#69, fixed to surface it); the API
  path was wrong, `/v2/firewall-groups/{id}/rules` instead of the correct
  `/v2/firewalls/{id}/rules` (#70); `OPERATOR_IP` is stored in Infisical as a CIDR
  (`x.x.x.x/32`) but Vultr's `subnet` field wants a bare IP (#71). **Caveat**: the very next
  dispatch after #71 got `HTTP 400 "This rule is already defined"` when creating the SSH
  rule — which may mean Vultr was tolerating the CIDR-suffixed value fine all along, so #71
  might not have been the actual fix (or might have been necessary and this is a separate,
  unrelated duplicate-rule collision from an uncleaned earlier attempt). **Not resolved
  either way** — say so plainly, don't claim #71 fixed it.
- Two `1b. Apply Infrastructure` runs (from PRs touching `infra/scan-vm-userdata.sh.tftpl`,
  which falls under `infra/**` even though it's not a `.tf` resource) needed operator
  approval mid-session (BI-D2's protected-Environment gate) — both resolved, nothing
  pending. Confirmed via `tofu plan`: this file being outside terraform's `templatefile()`
  means these applies had zero real resource diff.
- **No `/critic-gate` pass ran on any PR this session** (#62–#71) — all shipped as
  emergency incident-response fixes with only the local green gate + CI. Worth a look in
  retrospect once the live proof actually lands.

## Next

- **HITL Gate: OPEN — the next action needs the operator's own terminal.** A coder has no
  SSH client access or Vultr credentials locally; this cannot be done unattended.
- **SSH into a scan VM and find the real root cause.** One VM (label
  `bounty-scanner-30092621282-1`) may still be live from the pre-#71 attempt — check
  whether it's still up and reachable before dispatching a fresh one. Otherwise: dispatch
  `run-scan.yml` with `target_domain=scanme.nmap.org`, `program=SANDBOX-NMAP`,
  `image_tag=324b3fee8eb7aa168f812229efb60fa0c4045086` (or a newer `main` sha if `src/`
  has changed since), `enable_ssh_debug=true`, then SSH in as soon as "Create Vultr scan
  VM" completes (instance label is `bounty-scanner-<github.run_id>-1`, region `ewr`).
  Check: does `apt-get`/`docker` actually run at all, does the container start, can the VM
  reach S3/GHCR over the network, and `/var/log/cloud-init-output.log` for anything cloud-init
  itself logged before the script even ran.
- **Do not ship another speculative fix without live findings first.** Four rounds of
  blind code-review-driven fixes already happened this session (PRs #64–#66, plus #69–#71
  for the SSH tooling itself) — real bugs each time, but none of them were *the* bug that
  actually blocks the scan from completing. Get inside the VM before touching code again.
- Once the real cause is found and fixed, re-confirm the full live-proof DoD: VM boots,
  scan runs, findings land in S3 from the Vultr IP, status sentinel drives a clean exit,
  instance destroyed — against the REAL target (`ztna.myngc.com` / `DIB-VDP`), not just the
  sandbox one used for debugging.

## Queued behind the live proof

- **PR2 (teardown)** — delete the AWS Fargate/VPC/ECR/IAM estate as a destroys-only,
  summarized plan (BI-D2); docs pass; mark SE done; close #11. Only after the Phase-1 proof.
- **S2 — Scanner robustness** — follows SE (#11 is closed here; #14 only partly advanced via
  the status sentinel work this session).
  - **Idea, needs an architect planning pass (not coder-improvised):** an automated,
    always-on progress heartbeat — a lightweight *stage* marker written to S3
    (`runs/<RUN_ID>/progress.json`, tool name + timestamp only, no target-derived content —
    stays inside BI-D4) that `run-scan.yml`'s poll step reads and echoes each iteration.
    SSH debug (PR #68) now covers the same underlying need reactively (the operator can go
    look), but it's a heavier tool to reach for every time than an automatic signal would
    be. Still queued, still not built.
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
