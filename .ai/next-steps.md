# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Devcontainer (`DC`) — plan APPROVED, now `implementing`.** An owner-prioritised tooling task,
inserted ahead of SE. Assigned to **Sonnet / Coder** to build `.devcontainer/` per the approved
plan — greenfield, no config exists yet. Not a roadmap sprint.

## Just done

- **DC planning pass — COMPLETE (Opus/Architect), plan approved by owner (2026-07-22).**
  Wrote [sprints/DC_devcontainer/sprint_plan.md](../sprints/DC_devcontainer/sprint_plan.md).
  Two owner decisions locked:
  1. **Scanner runtime EXCLUDED** — `src/Dockerfile` stays the sole runtime definition; BI-D5
     migrates that runtime to Vultr anyway; unit tests use `tmp_path` and never shell to real tools.
  2. **Hybrid, pinned composition** — official `python`(3.11) + `github-cli` features (`:1`); a
     `Dockerfile` layer installs OpenTofu / tflint `v0.64.0` / gitleaks / zizmor / `yq` **pinned +
     SHA256-verified**; `jq` from apt; hatch baked in; Python **3.14 via `hatch python install`**.
- **Grounding pass caught two errors in the original scope note:** `tflint v0.64.0` is part of the
  `tofu-validate` required check (was missing from the note) and is now in-scope pinned to match CI;
  and the Python audit/sbom/lint tools are **hatch-provisioned**, so they need no OS install (keeps
  the Dockerfile layer small).

## Next

- **Build `.devcontainer/` (Sonnet / Coder).** Deliver `devcontainer.json` + `Dockerfile` per the
  plan's Task breakdown. **Acceptance test = the plan's Task 3 command set all green in a freshly
  built container** (hatch lint/test/audit/sbom; tofu fmt+validate+tflint; gitleaks; zizmor; hatch
  build on 3.14; gh/yq/jq resolve). Deferred judgment call (plan Task 4): root `.gitattributes`
  (`* text=auto eol=lf`) only if `git add --renormalize` shows no churn — record either way.
  Touch **only** `.devcontainer/**` (+ optional `.gitattributes`).
- **HITL Gate:** NONE OPEN — plan approved, build may auto-start. Next gate is the **owner merging
  the build PR** (the build session opens it and never self-merges).

## Queued behind the devcontainer

- **SE — Egress migration (BI-D5)** — the next *roadmap* sprint (retire ECS/VPC/ECR; per-scan Vultr
  VM; re-point `run-scan.yml`). SE before S2. Plan unwritten.
- **loop-orchestrator adoption (Phase 4)** — the plugin's second adoption, planned *in that repo*.

## Still-open operator gates (not sprints; a coder cannot do these)

- **S1: RoE documents don't exist yet.** Fail-closed scanner refuses until
  `s3://<findings-bucket>/roe/<program>/scope.json` exists per engagement (BI-D8/D9).
- **S1: UA contact URL** — confirm `https://hackerone.com/seuss` resolves (a 404 is worse than none).

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model (sprint sequence; BI-D1..D13).
- `sprints/DC_devcontainer/sprint_plan.md` — the approved DC plan (task breakdown + acceptance test).
