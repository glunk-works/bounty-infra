# Next steps — dev-workflow cursor

Thin, live cursor for whoever picks up this repo next. Points into the deep record
(`docs/hardening_roadmap.md`, the sprint plan, the issues) — it does not copy them.
Regenerate this at the end of every working session.

## Now

**S0 closed** (#6, #8, #9, #10 all remediated and behaviorally verified). **The compute-model
architecture pass is also done — BI-D5 is locked** (2026-07-21): scan egress leaves AWS for
per-scan ephemeral VMs on **Vultr**; AWS keeps the control plane. See
`docs/hardening_roadmap.md` § *RESOLVED — compute-model architecture decision*.

**SG-partial is done — three PRs, all merged** (2026-07-21): `dependency-audit`, `sbom`,
`pr-title` (#34); `zizmor` + full action pinning + `persist-credentials: false` (#35);
`secrets-scan` (#36) — `GITLEAKS_LICENSE` landed as a `glunk-works` org secret. `ci.yml` now
runs 9 jobs on every PR: `lint`/`test`/`package`/`tofu-validate`/`tofu-plan`/`dependency-audit`/
`sbom`/`secrets-scan`/`zizmor`, plus `pr-title` in its own workflow.

**Required-checks list caught up to match, same day** (2026-07-22): confirmed
`dependency-audit`/`sbom`/`secrets-scan`/`zizmor` green directly on `main`'s HEAD commit (via
the check-runs API, not just their own PRs), then added all four to the
`protected-integration-branches` required-status-checks list in one batch — PR #37 first
extended `ruleset-drift.yml`'s taxonomy to match (merged), *then* the live ruleset was updated
(never require a check the drift guard doesn't also watch). Verified via `workflow_dispatch`:
`ruleset-drift` reports `OK: ruleset intact — 4 rule types, 8 required checks.` `pr-title`
stays deliberately ungated — same BL-10 reasoning, unaffected by the three other SG additions
landing alongside it (confirmed by owner).

**S1 is planned as of 2026-07-22** (Opus pass, 5 micro-gates) — and it grew a prerequisite.
Plans: `sprints/S1_scanner_security_core/sprint_plan.md` and
`sprints/SC_scope_core_extraction/sprint_plan.md`. New decisions **BI-D6/D7/D8** in the roadmap.

**Next action — SC, then S1. Model Sonnet for both** (the specs exist; execute them):

1. **SC — extract `scope-core`.** Stand up `glunk-works/scope-core` from loop-orchestrator's
   `tools/scope_validator` + `tools/ingest.sanitize`, re-point loop-orchestrator, **delete its
   local copies**. Cross-repo, touches no bounty-infra `src/`. **Blocks S1.**
2. **S1 — #7 + #13 + #32** at the scanner boundary, consuming `scope-core`.

**SE** remains independent and unblocked if you'd rather do it first — but S1 was chosen
2026-07-22 and S1's *scanner code* is deliberately substrate-neutral, so SE will not invalidate
it (its IAM grant is a different story — see BI-D8's scope correction).

**Two OPERATOR actions gate S1 actually working, neither of which a coder can do:**
1. **The UA contact URL/email** (#32) — no default, and an unset contact is a deliberate startup
   error so an anonymous scanner can't ship by accident. Must be real and reachable; its whole
   purpose is giving an abuse desk somewhere to write.
2. **The RoE document itself** — a hand-authored JSON object in S3 holding real program scope.
   S1 ships the *mechanism*; until that object exists a fail-closed scanner correctly refuses to
   scan anything. **"S1 merged" and "scans work again" are two separate events.**

**Do not start the IaC security scan or the container image scan** — both are SG gates still
pending (not part of the four just closed above) that should follow SE (see the ordering note
in the roadmap's sprint sequence).

| Task | State |
|---|---|
| **T1** branch protection + method scaffold | ✅ ruleset · scaffold (#24) · required-checks list (landed with T3, PR #27) |
| **T2** gated OpenTofu deploy (#9) | ✅ **verified end to end** — plan no-op on PR; apply approved → applied (#25, #26) |
| **T3** non-bypassable CI (#8) | ✅ **done** (PR #27) — all 5 parts (a–e); see below |
| **T4** `run-scan.yml` injection fix (#6) + drop unused token (#10) | ✅ **done and verified end-to-end** (PR #29) — see below |

## Just done (2026-07-21) — T3, non-bypassable CI (#8), PR #27

- **(a)** `ci.yml` dropped its `paths:` filter — runs on every PR, no deadlock risk.
- **(b)** Split the old combined `validate` job into `lint` + `test` job ids, no
  `name:` overrides anywhere in `ci.yml` — job id is now exactly the required-check
  context.
- **(c)** New credential-free `tofu-validate` job: `fmt -check -recursive`,
  `init -backend=false && validate`, pinned `tflint` (`terraform-linters/setup-tflint@v6`,
  tflint `v0.64.0` — verified both tags exist via the GitHub API before pinning, since a
  wrong guess would have broken CI on the first run).
- **(d)** `build-image.yml` no longer pushes `:latest`. It pushes only
  `:${{ github.sha }}` and calls `aws ecs register-task-definition` directly to roll that
  image into a new task-definition revision — bypassing Tofu **on purpose** for just this
  field. `infra/main.tf`'s `aws_ecs_task_definition.scanner_task` now carries
  `lifecycle.ignore_changes = [container_definitions]` so Tofu stops reverting CI's
  rollouts on the next unrelated apply. New `variable "image_tag"` (default `"latest"`) is
  bootstrap-only — confirmed via a real `tofu-plan` run that this produces **zero diff**
  against current state (the default matches what's already deployed, so nothing broke).
  **This is a real architectural call, not literally spelled out in the sprint plan** — CI
  now owns image rollouts for this one field; BI-D2's plan+approval gate still covers
  everything else in that resource. User confirmed this design before it was pushed. If
  the OPEN compute-model question (Fargate/Docker vs. Ansible) is ever resolved, revisit
  this split.
- **(e)** Ported loop-orchestrator's `ruleset-drift.yml` structure, retargeted at this
  repo's 4-check taxonomy (`lint`, `test`, `tofu-validate`, `tofu-plan`) instead of
  loop-orchestrator's 8. Verified via `workflow_dispatch` against the live ruleset —
  passes clean (run 29859578890).
- **Required-status-checks applied to the live ruleset** (the piece T1 deferred): fetched
  loop-orchestrator's live `required_status_checks` parameters first
  (`strict_required_status_checks_policy: false`, `do_not_enforce_on_create: false`) and
  mirrored the shape exactly rather than guessing. Applied only after all 4 checks had
  already run green on PR #27 — never require a check that hasn't reported yet.
  `GET /repos/glunk-works/bounty-infra/rules/branches/main` now shows all 4 rule types
  (`deletion`, `non_fast_forward`, `pull_request`, `required_status_checks`) and all 4
  contexts.
- **Recovered a second stranded-commit incident** (same shape as the T2 one below, #26):
  `docs/s0-t2-verified-credential-model`'s final commit (this section's "point the cursor
  at T3" update) was pushed ~2 minutes *after* PR #26 squash-merged, so `main` never got
  it — this file's own "Now" section still read "START T3" as of a fresh `main` pull.
  Cherry-picked it onto the T3 branch before writing this update. **The gotcha below about
  checking `git log origin/<branch> --not main` before trusting a branch is done applies
  to reading this very file, not just deleting branches** — always diff against `origin/main`
  before trusting a cursor file's "Now" section.

## Previously done (2026-07-21)

- **Ruleset `protected-integration-branches`** (id `19438326`) active on `refs/heads/main`:
  `pull_request` + `deletion` + `non_fast_forward`, `bypass_actors: []`,
  `required_approving_review_count: 0`. Matches loop-orchestrator's field-for-field.
- **`docs/hardening_roadmap.md`** — reference of record (#20, #21, #22): posture,
  BI-D1..BI-D4, sprint sequence, public-repo rules, OPEN compute-model question.
- **Deleted `oidc-debug.yml` + `test_oidc.yml`** (#23) — an unpinned third-party action
  holding `id-token: write`, and an `aws sts get-caller-identity` echo into a
  world-readable public-repo log. One-off bring-up aids on no delivery path; **neither was
  covered by any issue or sprint**, so "covered by a finding" ≠ "reviewed."
- **T1 scaffold** (#24) — `CLAUDE.md` (routing layer + bounty-infra local conventions) and
  this cursor.
- **T2 gated deploy** (this PR) — `plan-infra.yml` (job `tofu-plan`, every PR, summary-only
  output) + `deploy-infra.yml` (job `apply`, `environment: production`). The `production`
  Environment is live: required reviewer `Seuss27`, `prevent_self_review: false`,
  deployments restricted to `main`. **Five deviations** from the plan as written are recorded
  in the sprint plan's T2 entry — read them before touching either workflow.
  **Both paths verified live 2026-07-21:** plan gave `tofu plan exit code: 0` (no-op against
  real state); apply parked for approval, was approved, authenticated, and applied a no-op.

## Credential model for the two infra workflows (verified end-to-end 2026-07-21)

Two OIDC hops, each validating independently: GitHub → Infisical (audience
`https://github.com/glunk-works/bounty-infra`), then Infisical's `AWS_*_ROLE_ARN` → AWS
(audience `sts.amazonaws.com`). **The two hops bind on different things** — that asymmetry
is the whole lesson of T2:

| Path | Infisical identity | Infisical binds on | AWS role | AWS trusts subject |
|---|---|---|---|---|
| plan (PR) | `vars.PLAN_IDENTITY_ID` | subject `:pull_request` | `github-actions-bounty-infra-plan` | `:pull_request` |
| apply (merge/dispatch) | `vars.IDENTITY_ID` | **claims** `repository` + `ref` | `github-actions-bounty-infra` | `:ref:refs/heads/main` **+** `:environment:production` |

**Why the apply identity binds on claims, not subject.** Adding `environment: production`
changed the job's `sub` to `:environment:production`, but that identity is shared with
`build-image.yml` and `run-scan.yml`, which still present `:ref:refs/heads/main` — and
Infisical's **Subject field holds one value** (globs, but no reliable list; a
comma-separated pair was tried and rejected with 403). A glob wide enough for both
(`repo:…:*`) would also match `:pull_request` and hand the apply identity to every PR.
So the binding moved to the claims that are **invariant to the environment**:

- `repository` = `glunk-works/bounty-infra`
- `ref` = `refs/heads/main`

Equivalent, not looser: for the non-environment workflows `sub` encodes exactly
`repository` + `ref`, so the same jobs are admitted plus the environment-gated apply. PR
runs still fail — their `ref` is `refs/pull/N/merge`.

The plan role is read-only, state-prefix-limited, and carries an explicit `Deny` on the
findings bucket. AWS side is code in `glunk-works/global-bootstrap` (`plan_roles.tf`);
**the Infisical side has no IaC** and was configured by hand — it is the one part of this
model that cannot be reviewed in a diff.

**Never merge the two identities.** Widening the apply identity to accept `:pull_request`
would make merely *opening* a PR grant apply-capable credentials with no approval —
workflow changes in a PR take effect for `pull_request` runs — re-opening #9 sideways.

## Just done (2026-07-21) — T4, `run-scan.yml` injection fix (#6) + drop unused token (#10), PR #29

- Rewrote the *Trigger Scan Task* step: all four `workflow_dispatch` inputs now ride `env:`
  (`inputs.*`, not `github.event.inputs.*` inline in `run:`), the ECS `--overrides` JSON is
  built with `jq -n --arg` instead of string-concatenated JSON, and a new **`Validate
  target_domain`** step runs a strict hostname regex before any AWS call. Also dropped the
  unused `GITHUB_TOKEN`/`GITHUB_REPOSITORY` container env vars and `issues: write` (#10) —
  confirmed via grep that `scanner.py` only ever reads `S3_BUCKET_NAME`, already supplied by
  the task definition itself, and makes no GitHub API call.
- **Verified behaviorally on `main`, not just read** (three dispatches, in order):
  1. A `'`-containing `target_domain` was rejected at the new `Validate target_domain` step
     — confirmed no `aws ecs run-task` call happened.
  2. A dispatch from the **PR branch** hit `401 Access denied: OIDC claim not allowed` at the
     Infisical step, before the domain check ever ran — expected, not a fix defect: this
     workflow's identity is bound to `ref: refs/heads/main` (see credential-model table
     above), so `workflow_dispatch` from a non-`main` ref can never get past secrets-fetch.
     **Behavioral verification of `workflow_dispatch`-only workflows has to happen after
     merge**, the same as T2's plan/apply gate.
  3. Post-merge, a real dispatch against `scanme.nmap.org` on `main` completed with
     `Task exited with code: 0` and findings exported to S3 — full round trip proven.
- **Two more bugs surfaced by that behavioral testing, both fixed in follow-on PRs (not part
  of #6/#10, discovered only because verification was behavioral):**
  - **PR #30 — duplicate entrypoint.** `src/Dockerfile`'s `ENTRYPOINT` is
    `["python", "-m", "bounty_scanner.scanner"]`. ECS `containerOverrides.command` replaces
    Docker `CMD` only — it does **not** touch `ENTRYPOINT` — so Docker always execs
    `ENTRYPOINT + CMD`. The override `command` array had *also* carried
    `"python", "-m", "bounty_scanner.scanner"` as its first three tokens since before this
    sprint, so the real container argv doubled the module invocation:
    `python -m bounty_scanner.scanner python -m bounty_scanner.scanner <domain> ...`. Python's
    own arg parsing eats the first `-m bounty_scanner.scanner`, leaving `sys.argv[1:] =
    ["python", "-m", "bounty_scanner.scanner", "<domain>", ...]` for the scanner's `argparse`
    — `domain` became the literal string `"python"`, and the stray `-m` token made `argparse`
    call `parser.error()` (container exit code 2). **Latent since the entrypoint became the
    module form (`f20b30f`, 2026-06-26)** — masked before T3(d) because a mutable `:latest`
    image could be stale relative to whatever `run-scan.yml` on `main` expected; T3(d)'s
    sha-pinned, CI-gated rollouts made the deployed image track the current commit exactly,
    which is what finally exposed it. Fix: override `command` now carries only
    `[$domain, "--severities", ..., "--timeout", ..., "--max-findings", ...]` — the image's
    `ENTRYPOINT` already supplies the interpreter/module prefix.
  - **`glunk-works/global-bootstrap` — missing `ecs:DescribeTasks`.** After #30 landed, the
    task still launched but the workflow's `aws ecs wait tasks-stopped` failed immediately
    with `AccessDeniedException` — the `github-actions-bounty-infra` role could `RunTask` but
    not `DescribeTasks`/`StopTask`. Fixed in `global-bootstrap` PR #2
    (`fix(iam): grant ECS task execution perms and the ECS service-linked role`), which had
    *already merged* before this was even hit (a coincidental same-day fix) but had not yet
    been **applied** — `global-bootstrap` has no CI/CD by design (state-bootstrapping repo,
    applied only from a local terminal with the owner's own AWS session; see its README).
    Owner ran `tofu apply` (1 IAM change) and the very next dispatch went green. **This is
    the second time in this session an AWS-side permissions gap blocked a `bounty-infra`
    workflow and the fix lived in a different repo** — see the credential-model note above
    about `global-bootstrap` owning every OIDC role; the same is true of the workload IAM
    policies attached to those roles.
- loop-orchestrator's `ruleset-drift.yml` (ported here in T3) was the cited in-house
  reference shape for the `env:`/`jq` pattern this task followed.
- **#6 blocks loop-orchestrator #18 — now unblocked.** Its `seed`/`token` dispatch inputs can
  ride this same safe `env:` + `jq --arg` pattern.

## Just done (2026-07-21) — the compute-model architecture pass (BI-D5)

The roadmap's OPEN compute question is **resolved**. Full record in
`docs/hardening_roadmap.md`; the short version and what surprised us:

- **The Fargate-vs-Ansible framing was wrong.** Compute was never the constraint — the toolset
  is pure userspace TCP, and Fargate at ~2.5¢ per 30-minute scan is *cheaper* than an always-on
  VPS. The real constraints are **network identity** (rotating, unregistrable AWS egress IP,
  causing silent WAF false negatives) and **blast radius** (an abuse suspension hits the account
  holding every `glunk-works` OIDC role).
- **Two claims were verified against primary sources rather than assumed**, and both turned out
  decisive: AWS's pentest policy scopes authorization to *"your AWS assets"* (third-party
  targets excluded, no researcher carve-out), and Fargate's
  `linuxParameters.capabilities.add` accepts **only `SYS_PTRACE`** — so the tempting
  "keep Fargate, tunnel egress through WireGuard for a stable IP" fix is structurally
  impossible, not merely awkward.
- **"Smaller provider = more permissive" is false**, and checking saved us from a real mistake:
  **Hetzner explicitly prohibits scanning foreign networks/IPs** and is the default cheap-VPS
  recommendation. Vultr won on AUP text — it *affirmatively permits* scanning "if explicitly
  authorized by the destination host and/or network", which is exactly what a program's RoE
  grants. DigitalOcean is the fallback (silent, not permissive).
- **New issue #32** — the scanner has no identifying User-Agent and no rate limiting on
  `httpx`/`nuclei`. Provider-independent, survives the migration, and belongs in S1 alongside
  #7/#13. Surfaced only because the AUP research forced the question "what actually stops an
  abuse complaint being filed."
- **Sprint sequence gained SG (CI gate expansion) and SE (egress migration)**, and **S2's #11
  is re-scoped** — it targets a Fargate task role BI-D5 retires.

## Just done (2026-07-22) — S1 planning pass (Opus, 5 micro-gates)

Produced `sprints/S1_scanner_security_core/sprint_plan.md` +
`sprints/SC_scope_core_extraction/sprint_plan.md`, and locked **BI-D6/D7/D8**. What surprised
us, in rough order of how much it changed the plan:

- **The record contradicted itself, and bounty-infra was the wrong half.** loop-orchestrator's
  sprint-45 plan says its scope validator + ingestion sanitizer were "**built once here and
  shared into the bounty loop**" and are "the concrete fix for `bounty-infra#7`/`#13`" — while
  BI-D3/`CLAUDE.md` said bounty-infra must write its own. Owner overruled BI-D3's no-shared-code
  clause → **BI-D6**: a dedicated `glunk-works/scope-core` package repo, both repos depend on
  it, neither depends on the other. **Read the other repo's sprint plans, not just its code** —
  the intent that resolved this was in prose, nowhere in the source.
- **Validating the input domain does not close #7 — the real fix is a pipeline stage.**
  `subfinder` enumerates from CT logs and passive DNS, which routinely return shared-CDN hosts,
  vendor subdomains, and third-party-owned hosts; today every one of those is probed by `httpx`
  and actively scanned by `nuclei` with no further check. So the scope check is a **filter
  between subfinder and httpx**, not a `validate_target(args.domain)` at the top of `main()`.
  This single finding is what turned S1 from a small change into a real sprint.
- **BI-D7 — the two inputs are different kinds of thing.** The dispatched domain is an
  *assertion of authority* (hard-fail, loud, before any subprocess); a discovered host is an
  *observation* (drop, count, continue). Hard-failing everywhere was rejected because one stray
  CDN hostname would kill valid scans until someone loosened the rules to make scans finish —
  **a control people are motivated to disable is not a control.**
- **BI-D8 — RoE moves to S3, not Infisical-at-runtime.** Handing the **scan VM** an Infisical
  identity would park a secrets-manager credential on the most exposed, most disposable machine
  in the system (BI-D5's whole point). S3 + existing KMS instead, Infisical holds only the
  pointer; the rules then **never transit CI at all**, including the `containerOverrides` JSON
  S0-T4 just hardened. Also survives BI-D5 untouched, since S3 + KMS are what AWS retains.
- **The upstream code left us a note we'd have missed.** `ScopeViolation`'s message embeds the
  candidate verbatim, and loop-orchestrator's own comment says a caller logging one from
  attacker-influenceable text "should sanitize it first." bounty-infra is that caller — so
  `sanitize()` must wrap the candidate before it hits a log line. It's in a **comment**, not the
  API, which is exactly the kind of thing a reimplementation would have silently dropped.
- **#32 folded into S1** — it lands on the same `run_recon_pipeline` argv the scope filter is
  being inserted into, so splitting it means reopening that function for a handful of flags.

**Then the plan was critiqued hard and revised (same day) — 17 findings, several were real
defects in the plan, not just ambiguity.** The ones worth carrying forward:

- **The RoE was specified as if one program = one ruleset. It isn't.** Operator runs
  **HackerOne + Bugcrowd**; only H1 has a researcher API. → **BI-D9**: normalized JSON keyed by
  program handle, using H1's *vocabulary* but not its API envelope (Bugcrowd must share the
  file), and a **required `--program` handle** so selection is explicit. Never search-all —
  a typo would silently borrow another program's authorization.
- **Verifying the H1 API surfaced a second out-of-scope source** — `scope_exclusions` is its own
  endpoint, separate from `eligible_for_submission: false`. Using only the latter would scan
  explicitly-excluded assets while believing we were compliant. **Verify vendor APIs; don't
  model them from memory.**
- **I had designed a parser-differential vulnerability.** `sanitize()` NFKC-normalizes, and NFKC
  rewrites hostnames (fullwidth `ｅxample.com` → `example.com`). Validating one form while
  scanning another is a validate/use mismatch. Invariant now explicit: **sanitize is
  display-only; validate and scan the exact same bytes.**
- **One enforcement point on a three-hop pipeline.** httpx→nuclei was unguarded; safe only
  because `httpx` doesn't follow redirects *today*. Adding `-follow-redirects` later would
  bypass scope with no test failing. Now three enforcement points.
- **The file's house style is except-and-continue** (`scanner.py:129-134`, `271-272`) — the
  exact opposite of BI-D8's fail-closed requirement. A coder pattern-matching the file would
  have silently defeated it.
- **`TriageReport` is Gemini's `response_schema`** — the obvious place to put the drop count
  would have changed what the model is asked to emit. Metadata goes to its own S3 artifact.
- **The distribution mechanism could have blocked every merge.** `dependency-audit` and `sbom`
  both scan the *installed environment* (deliberately not `skip-install`), and both became
  required 2026-07-22. A GitHub-tarball dep is unknown to both → **smoke-test in a scratch venv
  before committing to it.**
- **`git+https://` would break the image build** — only the Go builder stage installs `git`
  (`Dockerfile:3`); the runtime stage running `pip install .` has none. Tarball URL, not git URL.
- **Wildcard→regex is the sharpest risk in S1**: `re.escape` the literal, **anchor both ends**
  (scope-core uses `re.search`), apex excluded by default. Under-inclusive is safe;
  over-inclusive is unauthorized scanning.
- **Corrected an overclaim:** "S1 survives BI-D5 untouched" is true of the scanner code, **not**
  the IAM grant — that attaches to a Fargate role BI-D5 retires.

## Just done (2026-07-22) — required-checks catch-up, PR #37

- Precondition check first: `dependency-audit`/`sbom`/`secrets-scan`/`zizmor` all needed to be
  confirmed green **directly on `main`**, not just on #34/#35/#36's own PR runs — `ci.yml` only
  triggers on `pull_request` (no `push`), so there's no separate "run on main" event to point
  to. Resolved by querying `GET /repos/.../commits/{sha}/check-runs` against `main`'s HEAD
  commit directly: GitHub carries check-runs forward from a PR's head commit onto the new
  squash-merge commit on the base branch, so this is a real, checkable signal, not an
  assumption. All four came back `success`.
- **PR #37**: extended `ruleset-drift.yml`'s `missing_checks` taxonomy from 4 to 8
  (`lint`/`test`/`tofu-validate`/`tofu-plan` + the four above), merged before touching the live
  ruleset — same T3(e) discipline of never letting the drift guard and the ruleset it watches
  drift apart.
- Live `protected-integration-branches` ruleset (id `19438326`) updated via `gh api --method
  PUT` with the full ruleset body (fetched current state first, changed only the
  `required_status_checks` array, left `pull_request`/`deletion`/`non_fast_forward` and
  `bypass_actors` untouched) — same PUT-the-whole-object approach as every other ruleset edit
  this repo has done, since the endpoint has no PATCH-a-single-rule affordance.
- **`pr-title` decision**: asked the owner explicitly rather than assume — same BL-10 reasoning
  holds (title-format convention isn't a security/correctness gate), confirmed to stay ungated
  even with three more security gates landing alongside it.
- Verified via `workflow_dispatch` (run 29879933161, not just read back the API response):
  `ruleset-drift` logs `OK: ruleset intact — 4 rule types, 8 required checks.`
- **Also chased down a false stranded-commit alarm**: `git log origin/ci/secrets-scan --not
  origin/main` showed `5bc6ca0` (the cursor update recording secrets-scan's landing) as absent
  from `main` — looked exactly like the recurring "pushed after merge" incident logged
  elsewhere in this file. It wasn't: `5bc6ca0`'s author timestamp was *before* PR #36's merge
  timestamp, so it rode the squash-merge in under a new SHA; `diff --strip-trailing-cr` against
  `origin/main`'s copy of this file confirmed byte-for-byte identical content. **The
  stranded-commit check is timestamp-relative, not "is this exact SHA an ancestor of
  main"** — a squash always mints a new SHA for every commit on the branch, merged or not, so
  SHA-absence alone isn't evidence of loss; compare content or compare timestamps against the
  merge time.

## Just done (2026-07-21) — secrets-scan (gitleaks), PR #36, closing SG-partial

- `.gitleaks.toml` ported verbatim from loop-orchestrator (`useDefault = true`).
- Before adding the job, read gitleaks-action's actual `src/gitleaks.js` rather than trust its
  README — the default `GITLEAKS_ENABLE_COMMENTS`/`GITLEAKS_ENABLE_UPLOAD_ARTIFACT: true`
  raised an obvious question for a **public** repo: does a real detected secret get its
  cleartext value re-broadcast into a world-readable PR comment or artifact? **No** — the
  action hardcodes `--redact` on every invocation, unconditionally. Job log, SARIF artifact,
  and PR comment all omit the actual match; only rule id/file/line/commit sha ever appear.
  That's what made it safe to leave defaults alone rather than invent a deviation.
- No `pull-requests: write` granted (matches loop-orchestrator). The action's PR-comment step
  403s without it but that's caught and logged as a warning, not a job failure — the required
  check's pass/fail is the scan result itself.
- Verified: all 10 checks green on PR #36, `secrets-scan` itself in 6s — confirms the org
  secret authenticated correctly on first try.

## Just done (2026-07-21) — zizmor gate + full action pinning, ci/zizmor-and-pinning

Ran zizmor locally against `main` (post-#34) before touching anything: **46 findings** — 33
`unpinned-uses`, 10 `artipacked`, 3 `template-injection`. All resolved; local re-run is now
**0 findings, exit 0**, at the same `--persona=regular` the new CI job uses.

- **Every third-party action across all 6 workflows pinned to a commit SHA** (10 unique
  actions), each resolved via the GitHub API rather than guessed and cross-checked where
  possible: `actions/setup-python` and `actions/upload-artifact` resolved to the exact same
  SHAs loop-orchestrator already pins, which is real corroboration of the method, not
  coincidence.
- **Two actions (`aws-actions/configure-aws-credentials@v6`, `terraform-linters/setup-tflint@v6`)
  had `v6` as an *annotated tag object*, not a lightweight tag pointing straight at a
  commit** — the naive `git/ref/tags/<tag>` lookup returns the **tag object's own SHA**, which
  is not a valid commit to pin `uses:` against. Had to dereference
  (`git/tags/<tag-object-sha>` → `.object.sha`) to get the real commit. Worth checking
  `.object.type` explicitly for every action pinned this way in future — the failure mode
  (pinning to a tag-object SHA) would likely just break the workflow outright, so it's a
  loud failure rather than a silent one, but still wasted a CI run to discover.
- **`persist-credentials: false` added to all 10 `actions/checkout` steps** across every
  workflow.
- **Found and fixed a live `CLAUDE.md` violation T4 missed**: `build-image.yml`'s "Fetch ECR
  URL from State" step inlined `${{ env.TF_STATE_BUCKET }}` etc. directly into a `run:`
  block — the exact #6 pattern — while the near-identical steps in `deploy-infra.yml`,
  `plan-infra.yml`, and `run-scan.yml` already used the correct plain-shell-variable form.
  T4 only touched `run-scan.yml`, so this sibling was never in scope. Confirmed via
  Infisical's docs that `export-type: "env"` (the default, unoverridden anywhere here)
  really does inject secrets as process env vars before assuming the fix would work at
  runtime.
- **New `zizmor` job in `ci.yml`**, using `zizmorcore/zizmor-action` (pinned SHA, v0.6.0).
  Job-scoped `security-events: write` (not workflow-wide) so SARIF can upload to the
  Security tab — free on this public repo under GitHub Advanced Security. Verified by
  reading the action's actual `action.sh` (not trusting a fetched summary of its README,
  which claimed advanced-security mode "will not fail the build on findings" — **false**:
  the script does `exit "${exitcode}"` unconditionally, so a zizmor finding at or above the
  default threshold fails the job exactly like a failing test does).
- **Not yet a required check** — same discipline as every other gate in this repo: it has to
  report green on a real PR here first.

## Gotchas worth remembering

- **Never require a status check that does not exist yet** — it strands every open PR.
  **Resolved for T3's taxonomy** (`lint`, `test`, `tofu-validate`, `tofu-plan` — all
  required on `main` now), but the principle stands for whatever T4 or a later sprint adds.
- **Required checks match by check-run name = job id.** Do not add a `name:` override to a
  gated job — `ci.yml`'s jobs are bare (`lint`, `test`, `tofu-validate`) since T3; keep it
  that way.
- **`ruleset-drift.yml` must NOT be a required check and must NOT be a job in `ci.yml`** —
  a required check is required only because the ruleset says so, so making the drift guard
  required would un-require it the instant the ruleset it watches is deleted, silently, on
  the exact failure it exists to catch (loop-orchestrator FD2).
- **`build-image.yml` was the missing half of #8 — fixed in T3(d).** It used to push
  `:latest` to a `MUTABLE` ECR repo with no CI dependency, so merging any `src/**` change
  silently replaced production Fargate code. Now sha-pinned + CI-gated (see T3 above); the
  ECR repo itself is still `MUTABLE` (left alone — only the task-definition image
  reference and the tag scheme changed).
- **#6 verification is behavioral, not structural** — dispatch a `'`-containing
  `target_domain` and prove it is rejected, don't just eyeball the `jq` rewrite.
- **#6 blocks loop-orchestrator #18.** Its `seed`/`token` inputs must ride T4's safe
  `env:` + `jq --arg` pattern, so S0-T4 ships before #18.
- **`.ai/state.json` is git-ignored** — this file (`next-steps.md`) is what travels.
- **Never `paths:`-filter a workflow that hosts a required check** (T2 deviation (i)) — the
  filter and the requirement deadlock. Path awareness belongs *inside* the job, as a
  step-level `if:`, so the job always reports a conclusion.
- **Never upload `tfplan.bin` or a plan/apply body as an artifact or PR comment.** It
  embeds the account ID, bucket names, subnet/SG IDs and ARNs, and on a public repo
  artifacts are as world-readable as comments (BI-D4). Publish addresses + counts only.
- **Adding an `environment:` to a job CHANGES its OIDC subject.** GitHub's subject filters
  are ordered: an Environment wins over `pull_request`, which wins over the branch ref. So
  a job that gains `environment: production` stops presenting `:ref:refs/heads/main` and
  starts presenting `:environment:production` — invalidating its credentials at **both**
  hops. Changing a job's trigger or environment is a change to its **identity**. Where the
  verifier takes a list (the AWS trust condition) **append**, never replace, because
  sibling workflows on the same role still use the old subject; where it takes one value
  (Infisical's Subject) **bind on `repository` + `ref` claims instead** — they don't move
  when an environment is added. Never paper over it with a `repo:…:*` glob: that matches
  `:pull_request` too.
- **`deploy-infra.yml` self-triggers.** Its `paths:` filter includes its own file, so a PR
  that edits the workflow queues an apply on merge — even with no `infra/**` change. Useful
  (workflow edits get exercised immediately) but easy to misjudge: I predicted merging T2
  would not trigger an apply, and it did.
- **The `production` Environment is what makes `deploy-infra.yml` safe, not the YAML.**
  If `environment: production` ever names an environment that does not exist, GitHub
  auto-creates it **unprotected** and the apply runs unattended — silently re-opening #9.
- **Pushing to a branch after its PR merges silently drops the work — this has now
  happened three times in a row** (#25→#26, then again #26→#27, then again on #27's own
  branch, recovered by branching fresh from `main` rather than a third cherry-pick chain).
  The reviewer can merge the moment required checks go green; a cursor-file update queued
  right after tends to lose the race. **Before pushing a docs-only follow-up to an
  already-open PR's branch, check `gh pr view <N> --json state` first** — if it says
  `MERGED`, branch fresh from `main` instead of pushing more commits to the dead branch.
  And before trusting this file's own "Now" section, or deleting any merged branch, run
  `git log origin/<branch> --not origin/main` to make sure nothing on it is still stranded.
- Never commit to `main`, never merge your own PR, never force-push a pushed branch.
- **A squash-merge makes SHA-absence meaningless as a stranded-commit test.** `git log
  origin/<branch> --not origin/main` and `git merge-base --is-ancestor` both report *every*
  commit on *every* squash-merged branch as "not in main" — the squash mints a new SHA for the
  whole branch. Both gave false positives on 2026-07-22. Compare **content**
  (`diff --strip-trailing-cr`) or compare the branch's last commit **timestamp** against the
  PR's `mergedAt`; that is the check the gotcha above actually means.
- **`re.search`, not `re.match`, in `scope-core`.** Scope patterns are unanchored by design, so
  `example\.com` also matches `example.com.attacker.net`. Real RoE entries must anchor
  (`^example\.com$`). This is the most likely way a correct scope implementation still ends up
  scanning the wrong host, and it will not show up in any test that uses tidy fixtures.
- **`global-bootstrap` has no CI and applies only from a local terminal** — S1's
  `s3:GetObject`/`kms:Decrypt` grant lives there. A merged PR there is *code, not effect*.
  This has now blocked a workflow **three times** (T2 twice, T4 once); expect S1 Task 1's first
  real run to fail with AccessDenied and budget the manual apply.
- **"S1 merged" and "scans work again" are two separate events.** S1 ships the *mechanism*;
  the S3 object holding real program scope is an **operator action**. Until it exists, a
  fail-closed scanner correctly refuses to scan anything — right behavior, surprising at
  dispatch time if you haven't planned for it.
- **Read a hosting provider's AUP text before assuming it tolerates scanning — provider size
  is not the variable.** Hetzner, the default cheap-VPS recommendation, explicitly prohibits
  "scanning of foreign networks or foreign IP addresses." The distinction that matters is
  whether the AUP bans *unauthorized* scanning (fine — a program's RoE is the authorization) or
  *all* scanning (disqualifying). And AUP permission is not abuse-desk immunity: it makes an
  appeal winnable, it does not stop an automated complaint from killing the box. That is why
  #32 (attribution + rate limiting) matters more than the provider choice.
- **Fargate grants only `SYS_PTRACE`** via `linuxParameters.capabilities.add` — no `NET_ADMIN`,
  no `NET_RAW`. Rules out SYN-scanning tools *and* any tun-device VPN/tunnel inside a task. If a
  future design depends on network-layer control of egress, Fargate cannot host it at all.
- **ECS `containerOverrides.command` replaces Docker `CMD`, never `ENTRYPOINT`.** If the
  image's `ENTRYPOINT` already invokes the interpreter/module (`src/Dockerfile`:
  `["python", "-m", "bounty_scanner.scanner"]`), the override `command` array must carry
  **only** the module's own arguments — repeating the interpreter/module prefix there
  duplicates it in the real container argv (T4, PR #30). This bug was latent for weeks,
  masked by mutable `:latest` image staleness, and was only exposed once T3(d) made deployed
  images track the current commit exactly — a reminder that fixing one gate (sha-pinning) can
  surface bugs a looser previous state was accidentally hiding.
- **A `workflow_dispatch`-only workflow's identity can't be behaviorally tested from a PR
  branch.** `run-scan.yml` (and any workflow without a `pull_request` trigger) presents
  `ref: refs/heads/<branch>` when dispatched from a non-`main` branch, which the Infisical
  identity rejects (`401`) before the workflow body ever runs. Verify these behaviorally
  **after merge**, same discipline as T2's plan/apply gate — don't read a pre-merge dispatch
  failure as a defect in the change under test without checking which step it died on.
- **Workload IAM policies, like OIDC roles, live in `glunk-works/global-bootstrap`, not
  here — and that repo applies only from a local terminal, never CI.** `global-bootstrap` has
  no `.github/workflows/` by design (it bootstraps the state backend + IAM foundation other
  repos' CI depends on, so it can't depend on its own CI to deploy itself). A merged PR there
  is **code, not effect** until someone runs `tofu apply` locally with their own AWS session.
  Hit twice in T2 (OIDC subject/role) and again in T4 (`ecs:DescribeTasks`) — when a
  `bounty-infra` workflow fails on an AWS permissions error, check `global-bootstrap`'s
  `project_policies.tf`/`plan_roles.tf` before assuming the bug is local.

## OPEN — not scheduled anywhere

- ~~The four unadopted shared gates~~ and ~~the compute-model decision~~ — **both now
  scheduled**: SG and SE respectively in the roadmap's sprint sequence (2026-07-21).
- **The central conventions repo (BI-D3).** `CLAUDE.md` points at loop-orchestrator's
  `conventions.md` as the interim source; re-point once the central repo exists.
- **Infisical has no IaC.** Both machine identities are hand-configured and invisible to
  code review, unlike the AWS half (`global-bootstrap` Terraform). Lose or alter that config
  and nothing detects it — the failure surfaces as a 403 at deploy time. Infisical does ship
  a Terraform provider if this is ever worth closing.
- **`glunk-works/global-bootstrap`: the `ecs:RunTask` scoping is still inert.** `RunTask` is
  granted both in the ARN-scoped `AllowECSTaskExecutionAndMonitoring` statement and in the
  broad `Resource = "*"` statement (`project_policies.tf`), so the scoping restricts nothing.
  **Not fixed by global-bootstrap PR #2** — that PR added `DescribeTasks`/`StopTask` to the
  scoped statement (closing the T4 blocker) but left the broad statement's `RunTask` in
  place. Removing it from the broad list makes the scoping real (noted on
  global-bootstrap#2, never filed as its own issue).

## Pointers

- [`docs/hardening_roadmap.md`](../docs/hardening_roadmap.md) — reference of record.
- [`sprints/S0_governance_hardening/sprint_plan.md`](../sprints/S0_governance_hardening/sprint_plan.md)
  — the S0 plan (T1–T4, acceptance criteria, risks).
- Issues **#6–#14** (2026-07-19 review), **#18** (recon dispatch contract, cross-repo),
  **#19** (adopt the working method — this sprint), **#32** (scanner traffic attribution +
  rate limiting — S1, filed from the BI-D5 pass).
- **BI-D5** (compute model) — `docs/hardening_roadmap.md` § *RESOLVED — compute-model
  architecture decision* + the locked-decisions list.
- PRs **#29** (T4 injection fix + token drop), **#30** (duplicate-entrypoint fix, found via
  #29's behavioral verification); `glunk-works/global-bootstrap` **PR #2**
  (`ecs:DescribeTasks`/`StopTask` grant, applied 2026-07-21).
- Draft advisories `GHSA-59j8-c4rc-2jf4` (#6), `GHSA-pf9q-vx7g-f8gr` (#7),
  `GHSA-p3hr-h7cq-xp5m` (#13) — publish as each sprint closes.
