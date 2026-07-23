# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**SE — Egress migration (BI-D5) — is the next sprint, in `planning`.** No sprint plan exists
yet (`sprints/SE_egress_migration/` is unwritten). Assigned to **Opus / Architect** for the
planning pass. Scope (from the roadmap sprint table): retire ECS/VPC/ECR from `infra/**`;
per-scan ephemeral VM on **Vultr** with a reserved IP; re-point `run-scan.yml` at the new
launcher; S3-write credential path for the VM; provider abuse-team notification. Read
`docs/hardening_roadmap.md` § *BI-D5* (the compute-model decision + the primary-source
findings) before planning — it is also the threat model.

## Just done

- **SW (way of working) — COMPLETE, archived.** #19 closed. The method shipped as the
  `way-of-working` plugin (`glunk-works/claude-workbench`, tagged **v0.3.0**), adopted here via
  `.claude/settings.json` + `.ai/project.yml`. Task 5's 6 findings were dispositioned in
  claude-workbench PR #4 (merged, **WB-D6**): F1–F4 were a stale-`v0.1.0`-cache mirage (already
  fixed in v0.2.0), F5/F6 + a tier-3 coupling guard landed in v0.3.0. Pin bumped in
  bounty-infra #50 (merged, `58df368`). Full SW narrative: `.ai/archive/SW-next-steps.md`
  (local) + git history.
- **One SW live check still deferred:** the next fresh `/resume` must confirm the harness
  actually loads **v0.3.0** (the pin bump + stale-`cw_tag_checkout` clear only take effect on a
  new session's plugin load). If `/resume`'s text still shows loop-orch literals, the cache
  didn't re-fetch — see the [[plugin-tag-pin-not-honored-by-stale-cache]] memory.

## Next

1. **Plan SE (Opus/Architect)** — write `sprints/SE_egress_migration/sprint_plan.md`.
2. **Or, if prioritising the plugin rollout first:** **loop-orchestrator adoption (Phase 4)** is
   the immediate cross-repo follow-on, planned **in that repo** (delete its 7 local skills + 4
   shared agents, add `project.yml` + settings pinning `claude-workbench@v0.3.0`, keep
   `mutation-triage`/`live-verify` local, land Task 6's drift guard). Owner's call which comes
   first — SE advances bounty-infra hardening; Phase 4 proves the plugin's second adoption.

## Still-open operator gates (not sprints; a coder cannot do these)

- **S1: the RoE documents don't exist yet.** "S1 merged" ≠ "scans work" — a fail-closed scanner
  correctly refuses until `s3://<findings-bucket>/roe/<program>/scope.json` exists per engagement
  (BI-D8/D9). Hand-authored JSON, one object per HackerOne + Bugcrowd program.
- **S1: UA contact URL eyeball check** — confirm `https://hackerone.com/seuss` resolves (a 404
  contact is worse than none). Couldn't be verified programmatically (H1 profiles are JS-rendered).

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model (sprint sequence; BI-D1..D13).
- `sprints/SE_egress_migration/sprint_plan.md` — **to be written** (SE planning is the next task).
- Ordering: **SE before S2** (S2's #11 targets a role SE retires); SG's remaining 2 gates (IaC
  scan, image scan) follow SE. S1/SC/SW/S0/SG-partial all done.
