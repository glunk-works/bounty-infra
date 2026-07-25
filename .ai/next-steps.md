# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plans, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**S2 (scanner robustness) is the active frontier** — `planning`. **No sprint plan exists yet**
(`sprints/S2_scanner_robustness/` is unwritten), so the next pass is **from-scratch planning**,
one question at a time, to its own HITL gate before any `src/` change. Adopt **Opus /
architect**.

## Just done (this session, 2026-07-25)

- **Caught and corrected a major cursor drift.** The cursor claimed S1 was `planning` /
  "review-and-adopt then implement" — but **S1 was implemented and merged 2026-07-22** (PRs
  #40/#41/#42) and its code has been live on `main` for weeks. A prior session (PR #81) had
  re-pointed at S1 as if unstarted.
- **Verified S1 DONE.** Full green gate — 73 behavioral tests (every rejection asserts
  `subprocess.run` never ran), ruff + `bandit`, `tofu fmt`/`validate`. All five tasks meet
  their acceptance criteria. Two accepted residuals noted (NFKC-reject hardening; un-sanitized
  `severity` field) — neither a defect.
- **Reconciled issues:** closed **#7** (already), **#13**, **#32** (backfilled its empty body
  first). Filed deferreds **#82** (H1 RoE sync job) and **#83** (Bugcrowd hand-authored).
  Filed **#84** — the S1 live-smoke gap the hermetic suite can't close.
- **Recorded S1 DONE** in `docs/hardening_roadmap.md` (table row, ordering frontier, BI-D7
  realized marker) and **archived** S1's true final cursor to `.ai/archive/S1-next-steps.md`.
- **Advisories left draft** by decision (`GHSA-pf9q`/#7, `GHSA-p3hr`/#13, `GHSA-59j8`/S0).

## Next — plan S2 (from scratch)

Hold an **architect pass** (Opus) to design S2:

- **#12** — non-reproducible builds: `@latest` tools + unpinned nuclei templates/deps. Pin
  them. This is the constraint `CLAUDE.md` keeps citing ("do not add a `@latest` install while
  #12 is open").
- **#14** — pipeline reports success on partial/failed scans. Make the exit-code contract
  distinguish **partial** (e.g. hosts dropped out-of-scope) from **clean**. S1 already
  *records* the drop count (`scan_metadata.json`); #14 is about the exit code, not the data.
- **Decide** whether the two S1 residuals fold into S2 or stay as-is.
- **#11 does NOT belong to S2** — SE closed it (Fargate task role retired).

## ⚠ Uncommitted — commit this close-out

The archival edits are **not yet committed**: `docs/hardening_roadmap.md`, `.ai/state.json`,
this file, and `.ai/archive/S1-next-steps.md` (archive is git-ignored). Commit them as a
docs-only close-out PR (`/ship` or `/handoff`). `last_commit` in `state.json` is still the
pre-archival HEAD `9a8fecc`.

## Still-open operator gates (a coder cannot do these)

- **Author + upload a real RoE object** to `s3://<findings-bucket>/roe/<program>/scope.json`
  (BI-D8/D9) — prerequisite for any real scan and for **#84**. Until it exists a fail-closed
  scanner correctly refuses to scan.
- **S1 live smoke (#84)** — real `workflow_dispatch`; expect first-run `AccessDenied` until
  `global-bootstrap` applies the `s3:GetObject`+`kms:Decrypt` grant locally.
- **Publish the draft advisories** — when the operator chooses to disclose.
- **Reserved IP** (MG5) and **proactive Vultr abuse-team notification** (BI-D5).

## Open follow-ups (not sprint-gating)

- **#79** — drop `infra/`'s vestigial `provider "aws"` block once a fresh `tofu plan` confirms
  zero AWS state. **#76** — subfinder sources dark. **#8** — lint/test CI bypassed on
  push-to-main. **#10** — unused `GITHUB_TOKEN` in the scanner container.

## Pointers

- `docs/hardening_roadmap.md` — reference of record + threat model; SC/SE/**S1** now DONE.
- `sprints/S2_scanner_robustness/sprint_plan.md` — **to be written.**
- `sprints/S1_scanner_security_core/sprint_plan.md` — the (now-executed) S1 plan.
- S1 archive: `.ai/archive/S1-next-steps.md`.
