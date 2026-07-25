# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**S1 (scanner security core) is the next sprint, and it's UNBLOCKED** — `planning`. Its
only prerequisite, **SC (`scope-core` extraction), is DONE and deep-verified**. S1's plan
already exists (`sprints/S1_scanner_security_core/sprint_plan.md`, authored 2026-07-22), so
the next pass is **review-and-adopt**, not from-scratch planning.

## Just done (this session)

- **Archived SE** via `/archive-sprint` (both phases merged/applied/live-verified; final
  cursor snapshot at `.ai/archive/SE-next-steps.md`).
- **Discovered SC was already done** — it had been executed 2026-07-22 in the other two
  repos but never recorded here. **Deep-verified it (2026-07-25):**
  - `glunk-works/scope-core` (public) holds `scope_core/{rules,validate,sanitize}.py`, the
    four ported tests, a re-aimed import-boundary guard, and a live ruleset.
  - loop-orchestrator **deleted its local copies** and depends on scope-core via a PEP 508
    tarball direct-reference — merged as loop-orchestrator **#182**.
  - Shipped logic is **byte-identical** to the loop-orchestrator originals modulo import
    paths; the three security invariants hold (**fail-closed deny-wins**, **`re.search`
    unanchored**, **stdlib+pydantic import guard**, the last even unit-tests its own
    RED-ability); version floors correct; and the non-PyPI tarball dep **clears
    `dependency-audit`/`sbom` in real CI** (the SC plan's biggest flagged risk — did not
    materialize).
- **Recorded SC DONE** in `docs/hardening_roadmap.md` (sprint-table row, ordering note,
  BI-D6 realized-marker) and reseeded the cursor toward S1 — folded into **PR #81**.
- **Verified Dependabot PR #67** (github-actions group bump) all-green and merge-ready.

## Next — review-and-adopt S1, then implement

Hold an **architect pass** (Opus) over the existing S1 plan:

- **Confirm scope against live issue state:** #7 (reported CLOSED — re-confirm), **#13**
  (prompt-injection into Gemini triage, OPEN), **#32** (traffic attribution + rate limiting,
  OPEN).
- **S1 mounts scope-core's structural check at three points** — input gate, discovered-set
  filter, pre-nuclei revalidation (BI-D7) — over an S3-hosted HackerOne-vocabulary RoE
  (BI-D8/D9), plus triage-prompt hardening and scanner traffic attribution/rate limiting.
- **S1 Task 1 = "add the scope-core dependency"** — re-run the scratch-venv
  `pip-audit`/`cyclonedx` smoke test the SC plan specifies before merging it. It passed in
  loop-orchestrator, but bounty-infra is a *new* consumer with its own gate config.

## Awaiting your merge (human-merges bar)

- **PR #67** — Dependabot github-actions group bump; all 8 required checks green.
  `gh pr merge 67 --squash --delete-branch`
- **PR #81** — archive SE + record SC done (docs-only).

## Open follow-ups (not sprint-gating)

- **#79** — drop `infra/`'s vestigial `provider "aws"` block + `var.aws_region` once a fresh
  `tofu plan` on `main` confirms zero AWS resources remain in state.
- **#76** — subfinder ~30/37 sources dark (no API keys). S1/S2 scope.

## Still-open operator gates (a coder cannot do these)

- **Reserved IP** (MG5) — provision only when onboarding a program mandating source-IP
  registration.
- **Proactive abuse-team notification to Vultr** (BI-D5) — not yet done.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; SC and SE rows now DONE.
- `sprints/S1_scanner_security_core/sprint_plan.md` — the S1 plan to review-and-adopt.
- `sprints/SC_scope_core_extraction/sprint_plan.md` — the (now-executed) SC plan.
- SE archive: `.ai/archive/SE-next-steps.md`.
