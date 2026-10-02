# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record — it does
not copy it. Regenerate this at the end of every working session.

**Now:** S3 — MVP thin slice, `implementing`, due Fri 2026-10-30 (build order revised
2026-10-02). The plan is the milestone description's numbered build order (BI-D19), not
issue-number order.

**Just done (2026-10-02):**
- #110 exit-code contract merged (#163, `ae05427`).
- Org alignment review against 603-Identity/devcontainers: filed #164 (uv + lockfile, Python
  3.14), #165 (pre-commit + secret scanning), #166 (`src/Dockerfile` hygiene), #167 (adopt the
  org devcontainer template; left unmilestoned, blocked on devcontainers#10). Alignment notes
  added to #141, #134, #138.
- Secrets store: Infisical → AWS SSM Parameter Store decided; filed #168 and
  glunk-works/global-bootstrap#18 (read grants + KMS key). #102, #105, #107 now provision into
  SSM.
- plan-sprint placed #161, #162, #164, #165, #166, #168 in S3; the operator rewrote the
  milestone description with them in the build order (#165 joins the fallback line).
- First anchor for milestone 1 after that edit, description sha
  `50214dae3fea931b5d1fdb14742e3268dd82d152fb04ee99eaae3ab194c9ac11` (no prior `state.json`
  baseline to verify against).

**Next:** task #161 — fix the scan-VM status sentinel in `infra/scan-vm-userdata.sh.tftpl`:
failed setup stages record their real exit code (#161) and `docker run` gets a `timeout -k`
backstop (#162); one PR closing both. Model: `sonnet` (coder). **HITL Gate: OPEN** — first
anchor after the replan: a human "go" at `/way-of-working:resume` confirms the revised build
order before #161 starts. Operator gates (parallel, a coder cannot do these):
global-bootstrap#18 applied (gates #168), #102/#105/#107 secrets into SSM, #101,
global-bootstrap#13 applied locally.

**Pointers:**
- `docs/hardening_roadmap.md` — decisions BI-D1..D20 and the known-gap register.
- Sprint plan: https://github.com/glunk-works/bounty-infra/milestone/1
- `sprints/*/sprint_plan.md` — historical (S0–SW). No S2/S3 plan file exists by design.
