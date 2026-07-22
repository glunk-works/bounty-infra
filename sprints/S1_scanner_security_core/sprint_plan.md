### FILEPATH: /sprints/S1_scanner_security_core/sprint_plan.md

**Sprint Goal:** Close the scanner's three target-facing security gaps. **#7** — the scanner has
no structural scope check, so what it is allowed to touch is decided by who can click a button;
S1 makes scope a code-enforced invariant that no path can bypass. **#13** — target-derived text
flows into the Gemini triage prompt unfenced and unsanitized. **#32** — the scanner sends no
identifying User-Agent and applies no rate limiting, so a legitimate authorized scan is
indistinguishable from abuse at the receiving end. S1 is scanner-internal (`src/`) and
**provider-agnostic by construction** — it must survive BI-D5's Fargate→Vultr substrate change
untouched.

**Prerequisite: the SC pass must land first.** S1 consumes `glunk-works/scope-core`
(`sprints/SC_scope_core_extraction/sprint_plan.md`). Task 1 below is "add the dependency," so
there is nothing to start here until that package exists and loop-orchestrator has been
re-pointed at it.

**Out of scope:**
- **The egress migration (SE / BI-D5).** S1 changes no substrate. Every decision below is
  deliberately substrate-neutral so SE does not have to redo it — the RoE-delivery choice in
  particular (see **BI-D8**).
- **Robustness (#11 IAM, #12 pinning, #14 partial-vs-failed scans).** S2. **Watch the #14
  boundary carefully:** S1 introduces a legitimate new "scan completed but did less than you
  asked" state (hosts dropped as out-of-scope). S1 **records** that count as data; making the
  *exit-code contract* distinguish partial from clean is #14's job, not this sprint's.
- **Redesigning the shared primitives.** `scope-core` is consumed as-is. If S1 wants different
  semantics from `validate_target`, that is a change to `scope-core` with loop-orchestrator as
  a co-owner — not a local patch, and not a fork.
- **The reject-vs-escalate ladder (loop-orchestrator §6).** That repo's escalation machinery
  (`AWAITING_ISSUE`/`AWAITING_SLACK`) does not exist here and S1 does not build an analog.
  bounty-infra's answer to P0-D14 is **BI-D7** below — a two-tier reject policy, no escalation.
- **`banned_actions`.** `scope-core` ships `is_action_banned()` as a pure classifier, but this
  scanner has a **fixed argv** — it runs subfinder/httpx/nuclei and nothing else, with no
  model-selected or caller-selected action to classify. Wiring a classifier with no variable
  input to classify would be theatre. It becomes real when the toolset grows an aggressive
  action (§6 territory); revisit then.

**Context — decisions locked this pass (owner-confirmed via micro-gates, 2026-07-22):**
- **BI-D6** — shared code IS allowed, via a **dedicated small package repo** (`scope-core`),
  amending BI-D3's docs-only clause. Full rationale in the SC plan.
- **BI-D7** — **split out-of-scope policy: hard-fail the input, filter the discovered set.**
- **BI-D8** — **the scanner fetches its RoE from S3 at startup**; Infisical holds only the
  pointer.

Both BI-D7 and BI-D8 are recorded in `docs/hardening_roadmap.md`; the reasoning that produced
them is below, because it is the part that will not be obvious from the diff.

---

**Why this is a pipeline stage and not a one-line check (the finding that shapes the sprint).**

The current pipeline (`src/bounty_scanner/scanner.py:76-114`):

```
subfinder -d <domain>  ──►  subs_file   (discovered hosts)
                              │
httpx  ◄──────────────────────┘         (probes every one)
  └──► live_file
         │
nuclei ◄─┘                              (actively scans every live one)
```

**Validating only `args.domain` does not close #7.** `subfinder` enumerates from third-party
sources — certificate-transparency logs, passive DNS, public datasets. What it returns is
**not** guaranteed to be in the program's scope: CT logs routinely surface shared-CDN
hostnames, third-party SaaS vendor subdomains, and hosts owned by entirely different parties
that merely share a certificate. Today every one of those is probed by `httpx` and then
**actively scanned by `nuclei`**, with no further check anywhere. That is precisely the
unauthorized-scanning exposure #7 exists to close, and a single `validate_target(args.domain)`
at the top of `main()` leaves it fully open.

So the check has to exist **between subfinder and httpx**, as a filter over the discovered set.
That is the difference between a one-line fix and a real stage, and it is what Task 2 is
built around.

**BI-D7 — the two tiers, and why they differ.** `scope-core`'s `validate_target` always raises;
sprint 45 explicitly deferred the reject-vs-escalate *policy* to "whichever consumer issues
actions" (P0-D14). bounty-infra is that consumer, and the honest answer is that the two inputs
are not the same kind of thing:
- **The dispatched `target_domain` is an assertion of authority.** An operator (or, post-#18,
  loop-orchestrator) is claiming a program is in scope. If that claim is false it is an
  operator/orchestrator error and must be **loud** — `ScopeViolation`, non-zero exit, **before
  any subprocess runs**.
- **A discovered host is an observation, not a claim.** A CT log surfacing a CDN hostname is
  normal operation, not an error. Aborting the run on it would make scans of real programs
  fail constantly until the out-of-scope patterns were exhaustively tuned — pressure that ends
  with someone loosening the rules to make scans finish, which is the worst possible outcome
  for a safety control. So: **drop it, count it, carry on.**

Rejected: hard-fail everywhere (one stray CDN host kills a valid scan — a control people are
motivated to disable is not a control); filter everywhere (a typo'd or misdispatched target
silently yields a clean-looking empty report — the "green for the wrong reason" class S0 spent
an entire sprint eliminating).

**BI-D8 — RoE delivery, constrained from three directions at once.** The roadmap calls the
scope allowlist *"the most sensitive artifact this system holds"* (it enumerates which programs
the operator is engaged with), BI-D5 requires S1 to survive the substrate change, and the scan
VM is by design the most exposed and most disposable machine in the system.

That last constraint kills the most literal reading of "Infisical is the store": giving the
**scan VM** an Infisical machine identity would park a secrets-manager credential on the box
actively scanning third parties — exactly the machine most likely to be seized, abused, or
abuse-suspended. Wrong direction.

**Chosen:** the RoE lives in **S3 under the existing KMS key**; the scanner fetches it at
startup with the AWS credentials it already needs for findings upload; **Infisical holds only
the `s3://…` pointer**, which is not itself sensitive. The rules therefore **never transit
GitHub Actions at all** — no workflow log, no artifact, no PR comment, and notably **not** the
ECS `containerOverrides` JSON that S0-T4 just finished hardening. It also survives BI-D5
intact, because S3 + KMS are explicitly what AWS *retains*.

Rejected: env var carrying the rules (transits CI, lands readable in
`aws ecs describe-task-definition`, one careless `env` dump from exposure); `--scope-file` +
launcher materializes it (clean scanner-side seam, but on Fargate the file still has to arrive
via env-then-write, so it inherits the same exposure and adds a layer).

---

**Tasks:**

- **Task 1: Consume `scope-core`; load the RoE from S3, fail-closed (#7 groundwork, BI-D8)**
  - **Description:** Add the SHA-pinned `scope-core` dependency. New module
    `src/bounty_scanner/roe.py`: `load_scope_rules() -> ScopeRules`, fetching the RoE object
    from S3 (bucket/key from env, supplied from the Infisical pointer) and parsing it into
    `scope-core`'s `ScopeRules`.
  - **Fail-closed is the whole contract of this task.** If the RoE cannot be fetched, decrypted,
    or parsed, the scan **aborts non-zero before any subprocess runs**. It must never degrade to
    "no rules loaded → proceed." Note the belt-and-braces property that makes this robust:
    `ScopeRules` with an empty `in_scope_regex` **denies everything** by construction, so even a
    silent-empty bug fails safe rather than open — but the explicit abort is still required, so
    the failure is diagnosable instead of looking like "program has no assets."
  - **IAM:** `s3:GetObject` on the RoE key + `kms:Decrypt` for the existing key. **This lives in
    `glunk-works/global-bootstrap`, not here**, and that repo applies only from a local terminal
    — see Risks.
  - **Target Files:** `src/bounty_scanner/roe.py` (new), `src/pyproject.toml`,
    `src/tests/test_roe.py` (new); `global-bootstrap` `project_policies.tf`.
  - **Acceptance:** with a reachable RoE the rules load and parse; with the object absent,
    unreadable, undecryptable, or malformed the scanner **exits non-zero having spawned no
    subprocess** — asserted per failure mode, not just the happy path.

- **Task 2: Mount the scope check in the pipeline (#7, BI-D7)**
  - **Description:** Two enforcement points, per BI-D7.
    **(a) Input gate** — `validate_target(rules, args.domain)` **before any subprocess**;
    `ScopeViolation` → log → non-zero exit.
    **(b) Discovered-set filter** — a new stage between subfinder and httpx that reads
    `subs_file`, runs every host through `validate_target`, writes only survivors onward, and
    counts the drops. `httpx` and `nuclei` must be structurally incapable of receiving an
    unfiltered host: they read the **filtered** file, and the unfiltered one is never passed
    downstream.
  - **Sanitize before logging a `ScopeViolation`.** Its message embeds the candidate verbatim —
    upstream's own code comment flags this and names the caller as responsible: *"a … caller
    logging a ScopeViolation raised from attacker-influenceable candidate text should sanitize
    it first if that log is displayed/terminal-rendered."* bounty-infra **is** that caller and a
    discovered hostname is attacker-influenceable, so run the candidate through `sanitize()`
    before it reaches a log line. This is the one place the two primitives interlock, and it is
    easy to miss because it lives in a comment rather than the API.
  - **Log counts, not hostnames (BI-D4).** Dropped hosts are *resolved hosts* — S3 only, never a
    log. Emit `dropped N of M out-of-scope` at INFO; the dropped list itself goes to the S3
    artifacts alongside `subdomains.txt`.
  - **Target Files:** `src/bounty_scanner/scanner.py` (`run_recon_pipeline`, `main`),
    `src/tests/test_scanner.py`.
  - **Acceptance:** an out-of-scope `domain` exits non-zero with **`subprocess.run` never
    called** (assert on the mock, not on output); an in-scope domain whose discovered set
    contains out-of-scope hosts proceeds, and the argv/stdin `httpx` receives contains **only**
    in-scope hosts; the drop count reaches the report and the dropped hostnames reach **only**
    S3.

- **Task 3: Traffic attribution + rate limiting (#32)**
  - **Description:** Add an identifying **User-Agent** carrying a contact path, and rate/
    concurrency limits, to the `httpx` and `nuclei` invocations. Defaults must be conservative
    enough to be defensible to an abuse desk; make them configurable via CLI flags in the same
    style as the existing `--severities`/`--timeout`/`--max-findings`.
  - **Why this is here and not in S2.** It lands on the **same argv Task 2 is already editing**
    — same function, adjacent lines, same tests. Split across sprints, `run_recon_pipeline`
    gets reopened for a handful of flags. It is also thematically one change with #7: scope is
    "don't touch what you're not authorized to," attribution is "and when you do, be
    identifiable and gentle." Both are what makes an abuse complaint winnable — the BI-D5 pass's
    conclusion was explicitly that AUP permission is not abuse-desk immunity, which is *why*
    #32 exists.
  - **Verify the flags against the pinned tool versions, not from memory.** `httpx` and `nuclei`
    have both renamed rate-limit flags across releases; a wrong flag either errors out loudly or
    — worse — is silently ignored, leaving the scan unthrottled while the code claims otherwise.
    Confirm against the versions actually baked into `src/Dockerfile`.
  - **Target Files:** `src/bounty_scanner/scanner.py`, `src/tests/test_scanner.py`.
  - **Acceptance:** both tools are invoked with the UA and rate-limit flags (asserted on the
    argv); defaults are documented; **the flags are confirmed valid for the pinned tool
    versions**, not merely present in the argv list.

- **Task 4: Triage-prompt hardening (#13)**
  - **Description:** Three changes to `triage_findings()`:
    **(a)** run every target-derived field through `scope-core`'s `sanitize()` before it reaches
    the prompt — `matched-at`, and the template `name`/`description`/`template-id`, all of which
    are attacker-influenceable (a target controls what a template matches on, and a malicious
    template registry controls the rest);
    **(b)** structurally **fence** the untrusted block with explicit delimiters and an
    instruction that its contents are **data, never instructions**;
    **(c)** make "triage output is advisory" explicit and tested — the model's response must
    never feed a scope, authorization, or control-flow decision.
  - **(c) is a regression guard, not a fix.** Triage output is already inert today — it is
    printed and uploaded, nothing more. The point is to pin that property with a test **now**,
    while it is true, so a later change that lets triage influence what gets scanned trips a
    red test instead of quietly re-opening #13 at a much higher severity. This is the same
    reasoning as `ruleset-drift.yml`: guard the invariant while it holds.
  - **`response_schema` is not a defense here** — per #13 it constrains output *shape*, not
    *content*. A model told "report no findings" by injected text returns a perfectly
    schema-valid empty report. Do not treat the Pydantic schema as mitigating this.
  - **Target Files:** `src/bounty_scanner/scanner.py` (`triage_findings`),
    `src/tests/test_scanner.py`.
  - **Acceptance:** a finding whose `matched-at`/`name`/`description` carries ANSI escapes,
    zero-width/bidi characters, or an injected instruction reaches the model **sanitized and
    inside the fence** (assert on the actual `contents` passed to `generate_content`); the
    advisory-only property has a test that fails if triage output is ever wired into a decision.

**Definition of Done:** `hatch run lint:check` (ruff check + ruff format --check + `bandit -ll`)
and `hatch run test:run` both green, per `CLAUDE.md`. All 9 CI jobs green, including the four
gates that became required on 2026-07-22.

**Security Considerations:** S1 is the sprint where this repo stops relying on "only the right
person can press the button." Three notes that matter more than the diff:
- **The RoE content must never be committed, logged, or echoed** — not in a test fixture, not in
  a sample file, not in a docstring. Tests use invented rules (`^example\.com$`), never real
  program scope. A committed `scope.yaml` is the single worst artifact this repo could leak
  (BI-D4).
- **`re.search`, not `re.match`.** `scope-core` matches unanchored by design, so `example\.com`
  also matches `example.com.attacker.net`. Whoever authors the real RoE must anchor
  (`^example\.com$`). Call this out wherever the RoE format is documented — it is the most
  likely way a correct implementation still ends up scanning the wrong host.
- **Verification is behavioral, not structural** — this repo's hard-won S0 lesson (#6's fix was
  proven by dispatching a `'`-containing domain, and doing so surfaced two further latent bugs).
  Prove out-of-scope targets are rejected by observing that **no subprocess ran**, not by
  reading the code. Note the S0-T4 gotcha that applies again: `run-scan.yml` is
  `workflow_dispatch`-only, so an end-to-end dispatch test can only run **after merge**.
- Draft advisories `GHSA-pf9q-vx7g-f8gr` (#7) and `GHSA-p3hr-h7cq-xp5m` (#13) publish when S1
  closes.

**Risks & Blockers:**
- **SC must land first** — Task 1 has nothing to import until `scope-core` exists.
- **The IAM grant is in another repo that has no CI, and this has bitten three times.**
  `s3:GetObject`/`kms:Decrypt` live in `global-bootstrap`, which applies **only from a local
  terminal with the owner's own AWS session** — a merged PR there is *code, not effect*. T2's
  OIDC subject, T2's role, and T4's `ecs:DescribeTasks` all failed this exact way. Expect
  Task 1 to fail its first real run with an AccessDenied and budget for the manual apply.
- **The real RoE has to be authored and uploaded before any of this is live.** S1 delivers the
  *mechanism*; an S3 object containing the actual program scope is an **operator action**, and
  until it exists a fail-closed scanner correctly refuses to scan anything. That is the right
  behavior, but it means "S1 merged" and "scans work again" are two separate events — do not
  discover this at dispatch time.
- **Tool-flag drift (#12 territory).** Task 3 depends on `httpx`/`nuclei` flag names matching
  the pinned binaries. Unpinned or drifting tool versions would make a silently-ignored
  rate-limit flag possible — the failure mode where the code claims throttling it is not doing.
