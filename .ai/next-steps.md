# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Devcontainer (`DC`) — an owner-prioritised tooling task, inserted ahead of SE — in `planning`.**
Assigned to **Opus / Architect** for a **short plan first** (owner's choice), then a Sonnet
session builds `.devcontainer/`. No config exists yet; this is greenfield. Not a roadmap sprint —
an ad-hoc dev-environment task the owner chose over SE and loop-orchestrator Phase 4.

**Recommended scope (owner asked for best practice — the plan should refine, not just accept):**
green-gate toolchain on a **consistent Linux base**, deliberately **not** the scanner runtime.

- **Include:** Debian/Ubuntu base (kills the Windows/PowerShell/CRLF drift + `jq`-missing friction
  this repo keeps hitting); **Python 3.11 _and_ 3.14** (CI validates on 3.11 but packages on 3.14 —
  the #16 drift, worth pinning here); **hatch**; **OpenTofu**; a second tier of `jq` / `gitleaks` /
  `zizmor` / pip-audit / cyclonedx so the *full* CI runs locally pre-push.
- **Exclude the scanner runtime** (subfinder/httpx/nuclei/Go): `src/Dockerfile` already owns that
  deployment artifact; duplicating it bloats the image and creates a second definition to drift, and
  **BI-D5 migrates that runtime to Vultr VMs** anyway. Unit tests use `tmp_path` I/O and don't shell
  to the real tools.
- **Best practice:** compose from devcontainer **features** (`ghcr.io/devcontainers/features/python`,
  `/terraform`, …) over a hand-rolled Dockerfile where possible; keep it separate from `src/Dockerfile`.
- **The one open judgment call for the plan:** whether to add a scanner-runtime tier for local
  end-to-end smoke — the owner may want it; make the call explicit, don't default it away.

## Just done

- **SW (way of working) — COMPLETE, archived.** #19 closed; the `way-of-working` plugin
  (`glunk-works/claude-workbench`) is tagged **v0.3.0** and adopted here. Task-5 dispositions in
  claude-workbench PR #4 (**WB-D6**); pin bump + SW-close in #50; archival in #51 (`dd9121f`). Full
  narrative: `.ai/archive/SW-next-steps.md` (local) + git.
- **Deferred SW live check:** the next fresh `/resume` must confirm the harness actually loads
  **v0.3.0** (pin bump + stale-`cw_tag_checkout` clear only take effect on a new session's plugin
  load). If `/resume` still shows loop-orch literals, the cache didn't re-fetch — see
  [[plugin-tag-pin-not-honored-by-stale-cache]]. **This session ran the stale v0.1.0 skills**, so a
  clean v0.3.0 load next session is the proof.

## Queued behind the devcontainer

- **SE — Egress migration (BI-D5)** — the next *roadmap* sprint (retire ECS/VPC/ECR; per-scan Vultr
  VM; re-point `run-scan.yml`). SE before S2. Plan is unwritten.
- **loop-orchestrator adoption (Phase 4)** — the plugin's second adoption, planned *in that repo*.

## Still-open operator gates (not sprints; a coder cannot do these)

- **S1: RoE documents don't exist yet.** "S1 merged" ≠ "scans work" — fail-closed scanner refuses
  until `s3://<findings-bucket>/roe/<program>/scope.json` exists per engagement (BI-D8/D9).
- **S1: UA contact URL** — confirm `https://hackerone.com/seuss` resolves (a 404 is worse than none).

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model (sprint sequence; BI-D1..D13).
- `sprints/DC_devcontainer/sprint_plan.md` — **to be written** (or a lighter scope note; the plan
  session decides the ceremony level).
