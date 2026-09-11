# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record — it does
not copy it. Regenerate this at the end of every working session.

## Now

**S3 — MVP thin slice is the active sprint.** Planned 2026-09-11, **due Wed 2026-09-16**.
**The sprint plan is the GitHub milestone, not a local file (BI-D19):**
https://github.com/glunk-works/bounty-infra/milestone/1 — work its open issues in number order
(#98 upward). Decisions BI-D14..D20 are recorded by #100; until it merges, this file and the
issue bodies are the record.

Fallback line: if Tuesday looks bad, #118 (operator read path) and #119 (DefectDojo) drop
first; the persona registry (#112), governance mapping (#115), runbooks (#116) and the live
scan (#117) are the demo.

## Just done (2026-09-11)

- Verified build status: local green gate and CI on `main` both green; PR #97 merged.
- Planning pass, one question at a time, then a self-critique that changed four design points
  (GitHub Environment approval instead of Slack reaction polling; IAM grants verified day one;
  personas repo-local, not in the plugin; loop-orchestrator-vs-SDK left as a spike).
- Created milestones S3, S4, S5, SG, S6, S7 and issues #98–#151; attached the older open
  issues (#8 #10 #12 #14 #18 #76 #79 #82 #83 #84 #86 #87 #92) to milestones. S2 is dissolved
  into S3/SG.
- Cross-repo issues: global-bootstrap #13–#16 (grants, roles, Object Lock), claude-workbench
  #86 (`planning:` schema key), loop-orchestrator #204 and scope-core #3 (repo hygiene).

## Still-open operator gates (a coder cannot do these)

- #102 HackerOne API token into Infisical · #101 verification dispatch · #117 first live scan ·
  global-bootstrap #13 applied locally before #103 can run for real.

## Pointers

- Milestones: https://github.com/glunk-works/bounty-infra/milestones
- `docs/hardening_roadmap.md` — decisions BI-D1..D13 (D14..D20 land via #100).
- `sprints/*/sprint_plan.md` — historical (S0–SW). No S2/S3 plan file exists by design.
