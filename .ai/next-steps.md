# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record — it does
not copy it. Regenerate this at the end of every working session.

**Now:** S3 — MVP thin slice, `implementing`, due Fri 2026-10-30 (replanned 2026-10-02). The
plan is the milestone description's numbered build order (BI-D19), not issue-number order.

**Just done (2026-10-02):**
- Replanned S3 (plan-sprint): new due date; the description is now the operator gates, a
  14-step build order, the fallback line (#118/#119 drop first) and four BLOCKING items.
- Changes from the proposed order: #111 and #107 moved ahead of their producers/consumers,
  #105 added (recon-only finds nothing without it), #103 → #104 moved ahead of
  agents/governance (external dependency on global-bootstrap#13).
- Closed #98 and #92 as superseded (pin verified by SHA: `40d1a82` = `v0.15.0`); moved #151
  to SG.
- First anchor for milestone 1, description sha `e4d52042b47bdaea7a038028f4b6e457a134efc0c234348cc2c13ef50a4661bb`.

**Next:** task #110 — implement the exit-code contract (closes #14); PR #89 is input only.
Model: `sonnet` (coder). **HITL Gate: OPEN** — first anchor for S3: a human "go" at
`/way-of-working:resume` confirms the replanned build order before #110 starts. Operator gates
(parallel, a coder cannot do these): #102, #101, global-bootstrap#13 applied locally, #105's
source keys into Infisical.

**Pointers:**
- `docs/hardening_roadmap.md` — decisions BI-D1..D20 and the known-gap register.
- Sprint plan: https://github.com/glunk-works/bounty-infra/milestone/1
- `sprints/*/sprint_plan.md` — historical (S0–SW). No S2/S3 plan file exists by design.
