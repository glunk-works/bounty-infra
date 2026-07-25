# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**Between sprints — sprint selection (`planning`).** SE (egress migration, BI-D5) is DONE
and archived. No sprint is committed yet: the next unit is chosen by an **architect
planning pass**, one question at a time, before any plan is authored.

## Just done (this session)

- **Archived SE** via `/archive-sprint` — both phases merged, applied, and live-verified;
  HITL gate closed. Final SE cursor snapshot preserved at `.ai/archive/SE-next-steps.md`.
  Prior commit: `ddd2342` (Phase 2 teardown), cursor-sync `f1e64b6`.

## Next — select and plan the next sprint

Hold an **architect planning pass** (Opus) to **pick** the next sprint, then plan it. This
is a decision, not a default — re-check `sprints/*/sprint_plan.md` and each issue's live
state first. Candidates, with the live signal from the roadmap's sprint sequence + ordering
notes:

- **SC — `scope-core` extraction** — **strongest default.** BI-D6 makes it a *prerequisite*
  for S1, and the roadmap calls it "cheapest now" (loop-orchestrator's scope primitives
  still have zero live consumers). Plan exists: `sprints/SC_scope_core_extraction/sprint_plan.md`.
- **S1 — scanner security core** — #7 closed; **#13** (prompt-injection) and **#32**
  (traffic attribution / rate limiting) open. But BI-D6 says **SC lands first**. Plan
  exists: `sprints/S1_scanner_security_core/sprint_plan.md`.
- **S2 — scanner robustness** — **#12** (pin tools/deps), **#14** (partial/failed-scan
  detection). SE-before-S2 already satisfied. No `sprint_plan.md` yet.
- **SG — CI gate expansion** — five gates (`secrets-scan`/`dependency-audit`/`sbom`/
  `pr-title`/`zizmor`) are **already required** per the live ruleset; only the two
  AWS/infra-dependent scans (IaC security scan, container image scan) may remain, and those
  were sequenced to follow SE (now done). Confirm what's actually left before scoping. No
  `sprint_plan.md` yet.

## Open follow-ups (not sprint-gating)

- **#79** — drop `infra/main.tf`'s vestigial `provider "aws"` block + `var.aws_region` (and
  the matching workflow `-var=` flag) once a fresh `tofu plan` on `main` confirms zero AWS
  resources remain in state. Small, mechanical, deferred.
- **#76** — subfinder has ~30/37 sources dark (no API keys). Not urgent; S1/S2 scope.

## Still-open operator gates (a coder cannot do these)

- **Reserved IP** (MG5) — provision only when onboarding a program that mandates source-IP
  registration: flip `reserved_ip_enabled`, apply, register, dispatch with `use_reserved_ip=true`.
- **Proactive abuse-team notification to Vultr** (BI-D5) — not yet done.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; the "Sprint sequence"
  table and the ordering-notes paragraph after it drive the selection.
- Candidate plans: `sprints/SC_scope_core_extraction/sprint_plan.md`,
  `sprints/S1_scanner_security_core/sprint_plan.md`.
- SE archive: `.ai/archive/SE-next-steps.md`.
