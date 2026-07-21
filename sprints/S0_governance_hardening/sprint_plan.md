### FILEPATH: /sprints/S0_governance_hardening/sprint_plan.md

**Sprint Goal:** Stop the bleeding on the High workflow/governance findings and install the gate that makes every later fix safe. S0 stands up branch protection + a minimal working method, converts the ungated `push→tofu apply -auto-approve` deploy into a **plan-on-PR + Environment-approved apply** flow (#9), makes CI **non-bypassable** on all delivery paths (#8), and fixes the `run-scan.yml` **script-injection** surface (#6) while dropping the unused `GITHUB_TOKEN` (#10). This is the governance-first sprint (BI-D1); scanner security (#7/#13) is S1, robustness (#11/#12/#14) is S2. **S0 also unblocks loop-orchestrator S47's #18** — the recon dispatch contract adds inputs to the same `run-scan.yml` that #6 hardens.

**Out of scope:**
- **Scanner code (#7 scope, #13 triage).** No `scanner.py` change — S1. S0 is `.github/` + `infra/` CI/CD + repo governance only.
- **Robustness (#11 IAM, #12 pinning, #14 partial-success).** S2.
- **The central shared repo (BI-D3) and the compute-model / Ansible decision.** Both are their own passes (see the roadmap). S0's `CLAUDE.md` references loop-orchestrator's `conventions.md` as the **interim** convention source and notes the eventual central-repo migration.
- **The full method (skills, IaC security-critic agent, `architect-review` CI gate).** Interleaves across S1/S2 (MG1). S0 lands only the *minimal* method: `CLAUDE.md`, the `.ai/` cursor, the ruleset.

**Context — decisions (owner-confirmed via micro-gates, 2026-07-21; see `docs/hardening_roadmap.md`):**
- **BI-D1** governance-first · **BI-D2** gated deploy (plan-on-PR + apply-on-merge + `production` Environment approval; `-auto-approve` runs only post-approval) · **BI-D3** central shared repo is the long-term convention/code source (interim: reference loop-orchestrator).

**Tasks:**

- **Task 1: Branch protection + minimal working-method scaffold**
  - **Description:** Install a branch-protection ruleset on `main`: require a PR to merge, require ≥1 review, block force-push + deletion, **no bypass**. Turn on the *structural* protection **first** (PR + review + no-force-push — no check dependency) so every subsequent S0 PR is gated from the start; the **required-status-checks list is finalized at the END of S0** (T2/T3 create the checks — required checks match by job-id name, so they can't be required before they exist). Scaffold the minimal method: a lean `CLAUDE.md` (routing layer, referencing the shared Global Conventions + a bounty-infra section: OpenTofu `fmt`/`validate`/`tflint` + plan-gate, Actions `env:`+`jq` no-inline-`${{ }}`, scanner DoD ruff/bandit/pytest + pinned tools), the `.ai/` cursor (`state.json` + `next-steps.md`), and `sprints/` + `docs/hardening_roadmap.md` (already drafted).
  - **Target Files:** the ruleset (`gh api repos/glunk-works/bounty-infra/rulesets` — needs admin), `CLAUDE.md`, `.ai/state.json`, `.ai/next-steps.md`, `docs/hardening_roadmap.md`, `sprints/S0_governance_hardening/sprint_plan.md`.
  - **Acceptance:** `main` requires a reviewed PR to merge and rejects force-push/deletion; `CLAUDE.md` + `.ai/` cursor exist and point at the shared conventions; the required-status-checks list is applied once T2/T3's checks exist (deferred to S0's final step).

- **Task 2: Gated OpenTofu deploy (#9)**
  - **Description:** Replace `deploy-infra.yml`'s `push→apply -auto-approve` with two gates. **(a)** A `tofu plan` job on **PRs touching `infra/**`** — `tofu fmt -check`, `tofu validate`, `tflint`, then `tofu plan` with output posted (PR comment or uploaded artifact) so the reviewer reads the plan. **(b)** An **apply job on merge-to-main** that targets a protected GitHub **`production` Environment** (required reviewer); `tofu apply -auto-approve` runs **only after** the environment approval. Create the `production` Environment with required reviewers.
  - **Target Files:** `.github/workflows/deploy-infra.yml` (split into plan-on-PR + apply-on-merge), possibly a new `plan-infra.yml`; the GitHub `production` Environment (settings/API).
  - **Acceptance:** a PR touching `infra/**` runs fmt/validate/tflint/plan and surfaces the plan; merge to main does **not** apply until a required reviewer approves the `production` environment; no path applies infra without a visible plan + an approval. Existing deploys still succeed through the new flow (verify against a no-op plan).

- **Task 3: Non-bypassable CI (#8)**
  - **Description:** Extend `ci.yml` so the delivery path can't skip it: run on **all relevant paths** (add `infra/**` → the tofu fmt/validate/tflint checks, and keep `src/**`), and make the CI jobs **required checks** in the T1 ruleset so a direct-to-`main` push (now blocked anyway) and any PR must pass them. Ensure the deploy (T2) is **gated on CI green**. Optionally reconcile the `ci.yml` py-3.11-validate / py-3.14-package drift (the closed #16) if trivial.
  - **Target Files:** `.github/workflows/ci.yml` (paths + an infra-validate job), the ruleset required-checks (finalized here / with T1).
  - **Acceptance:** CI runs on both `src/**` and `infra/**` changes; the CI jobs + the `tofu plan` check are **required** on `main`; no merge can bypass them; the deploy flow depends on CI passing.

- **Task 4: `run-scan.yml` injection fix (#6) + drop unused token (#10)**
  - **Description:** Rewrite the *Trigger Scan Task* step so **no `${{ github.event.inputs.* }}` is interpolated inline into a `run:` shell block.** Pass all four inputs via an `env:` block; build the ECS `--overrides` JSON with **`jq -n --arg`**, referencing quoted `"$TARGET_DOMAIN"` etc. Add a **strict hostname regex** validation on `target_domain` before use (reject malformed input early — a structural check, distinct from S1's full RoE scope in the scanner). **Remove the unused `GITHUB_TOKEN` env var and the `issues: write` permission** (#10 — the scanner uploads to S3 and makes no GitHub API call). **Verify with a `'`-containing `target_domain`** that it is rejected/neutralized, not executed.
  - **Target Files:** `.github/workflows/run-scan.yml`.
  - **Acceptance:** dispatch inputs are consumed via `env:` + `jq --arg`, never inline `${{ }}` in `run:`; a `target_domain` containing a single quote does not break out (verified); `target_domain` is hostname-validated; `GITHUB_TOKEN`/`issues: write` are gone; the workflow still launches a scan correctly for a valid domain. **This clears the #6 precondition on loop-orchestrator #18** (its `seed`/`token` inputs then ride this safe pattern).

**Security Considerations:** S0 is entirely defensive. The three High findings (#6/#8/#9) are the "green for the wrong reason" class — an unprotected `main`, a CI that doesn't run on the delivery path, and an auto-apply with no plan. Fixing them **first** is what makes S1/S2's security fixes trustworthy (they land through a real gate). #6 is a live RCE-with-AWS-creds surface — treat T4 as the highest-priority individual fix. No new secret, no new external surface.

**Risks & Blockers:**
- **Admin scope needed** for the ruleset (T1) and the `production` Environment (T2). If unavailable, T1/T2 can't complete — surface early.
- **The apply-gate must not break live infra delivery.** Test the new plan/apply split against a **no-op plan** before relying on it; a mis-split could strand `main`→infra.
- **Required-checks sequencing** — never require a check that doesn't exist yet (it strands the requirement). Apply the required-status-checks list only after T2/T3's jobs have run once (finalize at S0's end).
- **#6 verification is behavioral, not just structural** — prove a quote-containing input is neutralized; don't just eyeball the `jq` rewrite.
- **Method discipline from here:** every S0 change lands via a reviewed PR (branch cut from `main`, never pushed to `main`); never merge your own PR; the human's merge is the approval.
