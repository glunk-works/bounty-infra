# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Egress migration (`SE`, BI-D5) — `implementing`.** Task 5 (the live proof) is still
**not met**. Five bootstrap-robustness fixes landed in the prior session, but the scan
pipeline still never completes on a live VM — root cause unknown. A live SSH-debug
session (this session) ruled out both suspects it could reach (firewall rule, SSH
agent) without ruling out the underlying problem — see below.

## Just done (this session — live SSH-debug attempt, no code changed)

- Dispatched `run-scan.yml` (`enable_ssh_debug=true`, `target_domain=scanme.nmap.org`,
  `program=SANDBOX-NMAP`, `image_tag=324b3fee8eb7aa168f812229efb60fa0c4045086`) — run
  [30096921939](https://github.com/glunk-works/bounty-infra/actions/runs/30096921939),
  active ~13:27–14:02Z, VM `bounty-scanner-30096921939-1` @ `45.77.101.242`.
- **~10 SSH connection attempts over ~30 minutes, effectively 0 successful logins**
  (one anomalous host-key-fingerprint prompt, never followed by a completed shell).
  Two suspects were raised and both were **cleared**:
  - *SSH agent* — Bitwarden's ed25519 agent (`jared.groves.2`) confirmed working via
    `ssh-add -l`, which listed the correct key. Not the cause.
  - *Firewall rule* — the operator pulled up the Vultr dashboard directly and confirmed
    the shared firewall group (`bounty-scanner egress-only`) held exactly **one**
    correctly-scoped rule (`Accept SSH 22 from 70.105.250.102/32`), attached to the
    right instance, no stale/duplicate rules. Not the cause.
- **With both access-layer suspects cleared, the leading hypothesis shifted to the VM
  itself** — its networking, or its boot generally, may never be fully coming up. This
  would unify with the original still-unsolved mystery (the recon pipeline never
  completing, zero status sentinel across 4 prior dispatches) under one root cause
  instead of two unrelated ones.
- A prior session's attempt at Vultr's web console/noVNC failed on what looked like a
  Vultr-side proxy issue (instance API showed `running` at the time).
- VM was torn down automatically by the Destroy step at the poll deadline (~14:02Z);
  nothing further to inspect on that specific instance.
- **Researched Vultr's console/noVNC requirements directly** (docs.vultr.com) to check
  whether the scan VM is missing something needed for console access to work:
  - Console access is 100% hypervisor-side (a noVNC view of the guest's virtual
    framebuffer) — it needs **no agent or VNC software running inside the guest OS or
    the scan container**. There is nothing to add to `scan-vm-userdata.sh.tftpl` or
    `src/Dockerfile` for this; the premise that something was "missing" was wrong.
  - The prior session's console failure almost certainly wasn't a real bug: per
    [Vultr's Web Console FAQ](https://docs.vultr.com/vultr-web-console-faq), the
    noVNC page's own **`Connect` button does not work for Vultr servers** — you must
    click **`Restart Server`** from inside the Vultr Console view itself to get it to
    attach. If that still fails: ping the IP, run an MTR report, then open a Vultr
    support ticket with those results (Vultr's own documented escalation path).
  - Cloud Compute instances have **no documented VNC API endpoint** (only bare-metal
    does: `GET /v2/bare-metals/{id}/vnc`) — console access can't be scripted into
    `run-scan.yml` and stays a manual, dashboard-only (my.vultr.com), HITL step no
    matter what.

## Just done (prior session — an incident-response chain, not planned work)

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

- **HITL Gate: OPEN — the next action needs the operator's own terminal/Vultr dashboard.**
  A coder has no SSH, Vultr console, or Vultr API credentials locally; this cannot be done
  unattended.
- **SSH debug's firewall rule and the SSH agent are both CLOSED leads — do not
  re-investigate either.** Both were directly verified correct this session (see above).
  Re-litigating them would waste the next live-debug window.
- **Get eyes on the VM's actual boot state via Vultr's web console (my.vultr.com) —
  `enable_ssh_debug` is not required for this, console access needs no ingress rule.**
  Dispatch a fresh run, open the instance's console tab, and if it says "Failed to
  connect to server": do **not** click the noVNC `Connect` button (confirmed
  documented-broken for Vultr) — click **`Restart Server`** inside the console view
  instead. That should show the actual boot sequence directly, independent of network
  reachability entirely. If it still won't connect: ping the IP, run an MTR report, open
  a Vultr support ticket with both. Do not propose adding VNC software to the VM or
  container — confirmed this needs nothing inside the guest.
- **Do not ship another speculative fix without live findings first.** This is now the
  second session where live access work (not code) was the actual constraint — the prior
  session's PRs #64–#66 and #69–#71 each fixed a real bug but none was *the* bug. Get
  inside the VM (via console, not SSH) before touching code again.
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
