### FILEPATH: /sprints/S1_scanner_security_core/sprint_plan.md

**Sprint Goal:** Close the scanner's three target-facing security gaps. **#7** — the scanner has
no structural scope check, so what it is allowed to touch is decided by who can click a button;
S1 makes scope a code-enforced invariant that no path can bypass. **#13** — target-derived text
flows into the Gemini triage prompt unfenced and unsanitized. **#32** — the scanner sends no
identifying User-Agent and applies no rate limiting, so a legitimate authorized scan is
indistinguishable from abuse at the receiving end. S1 is scanner-internal (`src/`) plus the
minimum `run-scan.yml` plumbing to carry two new arguments.

**Prerequisite: the SC pass must land first.** S1 consumes `glunk-works/scope-core`
(`sprints/SC_scope_core_extraction/sprint_plan.md`). Task 1 is "add the dependency," so there is
nothing to start here until that package exists and loop-orchestrator has been re-pointed at it.

**Out of scope:**
- **The HackerOne sync job.** S1 ships enforcement against a **hand-authored** RoE document
  (BI-D9). Automating the H1 pull is a follow-on task — see *Deferred* below.
- **The egress migration (SE / BI-D5).** S1 changes no substrate. **Correction to an earlier
  claim:** S1's *scanner code* survives BI-D5 untouched, but its **IAM grant does not** — the
  `s3:GetObject`/`kms:Decrypt` permission attaches to a Fargate task role BI-D5 retires, so SE
  re-points it. Do not read "S1 is provider-agnostic" as covering the credential path.
- **Robustness (#11 IAM, #12 pinning, #14 partial-vs-failed scans).** S2. **Watch the #14
  boundary:** S1 introduces a legitimate "scan completed but did less than you asked" state
  (hosts dropped as out-of-scope). S1 **records** that count as data; making the *exit-code
  contract* distinguish partial from clean is #14's job.
- **Redesigning the shared primitives.** `scope-core` is consumed as-is. Wanting different
  semantics from `validate_target` is a change to `scope-core` with loop-orchestrator as
  co-owner — not a local patch and not a fork.
- **`banned_actions`.** `scope-core` ships `is_action_banned()` as a pure classifier, but this
  scanner has a **fixed argv** — subfinder/httpx/nuclei and nothing else, with no
  caller-selected action to classify. Wiring a classifier with no variable input would be
  theatre. Revisit when the toolset grows an aggressive action.
- **CIDR / IP-range assets.** Excluded by the asset-type allowlist (T2). `scope-core` decides on
  regexes and this pipeline is domain-driven (`subfinder -d`), so IP ranges have no meaningful
  path through it today.

**Context — decisions locked this pass (owner-confirmed via micro-gates, 2026-07-22):**
**BI-D6** shared code via `scope-core` · **BI-D7** split out-of-scope policy · **BI-D8** RoE
fetched from S3 · **BI-D9** RoE schema modeled on HackerOne structured scopes, normalized,
program-keyed, with **explicit program selection**. All four are in `docs/hardening_roadmap.md`.

---

## The finding that shapes the sprint

Current pipeline (`src/bounty_scanner/scanner.py:76-114`):

```
subfinder -d <domain>  ──►  subs_file   (discovered hosts)
                              │
httpx  ◄──────────────────────┘         (probes every one)
  └──► live_file                        (URLs)
         │
nuclei ◄─┘                              (actively scans every live one)
```

**Validating only `args.domain` does not close #7.** `subfinder` enumerates from third-party
sources — certificate-transparency logs, passive DNS, public datasets — which routinely return
shared-CDN hostnames, third-party SaaS vendor subdomains, and hosts owned by entirely different
parties that merely share a certificate. Today every one is probed by `httpx` and then
**actively scanned by `nuclei`**, with no further check anywhere. A single
`validate_target(args.domain)` in `main()` leaves that fully open.

So the check is a **filter over the discovered set**, between subfinder and httpx — a pipeline
stage, not a line.

**Enforce at both boundaries, not just the first.** `httpx` output feeds `nuclei`. Today
`httpx -silent` does not follow redirects, so its output hosts are a subset of its input and
the single filter is *currently* sufficient. That is a property of today's flags, not of the
design: the day someone adds `-follow-redirects`, scope enforcement is silently bypassed
end-to-end and **no test fails**. Re-validate `httpx`'s output before it reaches `nuclei`. It
is nearly free and it removes the whole class.

---

## BI-D9 — the RoE document

**Modeled on HackerOne's structured scopes, but our own normalized schema.** The operator runs
programs on **HackerOne and Bugcrowd**; only HackerOne has a researcher-facing API. Bugcrowd
programs are therefore hand-authored and must live in the same document, and the scanner must
not couple to a vendor envelope a second platform will never match. So we adopt HackerOne's
**vocabulary** — `asset_type`, `asset_identifier`, `eligible_for_submission` — as the schema,
not its API response shape.

**Format: JSON.** Not YAML — YAML means adding PyYAML, a new supply-chain dependency while #12
is open, and `CLAUDE.md` forbids adding installs in that state. JSON needs no new dependency.

**Keyed by program handle, with explicit selection.** `run-scan.yml` gains a **required
`program` input**, passed to the scanner as `--program <handle>`; the scanner validates
`target_domain` against **that program's rules only**.

**Never search all programs for one that matches.** Two programs matching the same domain is
ambiguous, and a typo would silently borrow a different program's authorization. Explicit
selection also strengthens BI-D7: the dispatcher now asserts *both* "this program" and "this
domain," and a **mismatch between the two hard-fails** — which is the single most likely
real-world operator error this sprint can catch.

Shape (illustrative — T1 pins the real one):

```json
{
  "version": 1,
  "programs": {
    "acme": {
      "platform": "hackerone",
      "handle": "acme",
      "synced_at": "2026-07-22T00:00:00Z",
      "scopes": [
        { "asset_type": "WILDCARD", "asset_identifier": "*.acme.com",
          "eligible_for_submission": true },
        { "asset_type": "URL", "asset_identifier": "shop.acme.com",
          "eligible_for_submission": false }
      ]
    }
  }
}
```

**Verified against the live API 2026-07-22.** The structured-scope fields above are real
(`GET /hackers/programs/{handle}/structured_scopes`; HTTP Basic auth). **The fetch surfaced a
second endpoint that is easy to miss and would be a real hole: `GET
/hackers/programs/{handle}/scope_exclusions`.** There are therefore **two independent sources of
out-of-scope** — `eligible_for_submission: false` *and* the exclusions endpoint — and both must
land in `out_of_scope_regex`. Missing the second means scanning explicitly-excluded assets while
believing we are compliant.

**Credentials never reach the scan VM.** The H1 token is consumed only by the (deferred) sync
job in Actions with an Infisical-sourced credential — never by the scanner. Same argument that
rejected Infisical-on-VM in BI-D8: that box is the most exposed and most disposable machine in
the system, and an H1 token can read programs and file reports.

---

**Tasks:**

- **Task 1: RoE document — schema, S3 load, program selection (BI-D8/D9)**
  - **Description:** Add the SHA-pinned `scope-core` dependency. New `src/bounty_scanner/roe.py`:
    load the JSON RoE object from S3, select the program named by `--program`, and hand that
    program's scopes to T2's translator. New CLI args `--program` (required) and `--scope-uri`.
  - **Plumbing (do not skip — nothing supplies these today):** `run-scan.yml` currently builds
    `containerOverrides` with **`command` only** and no `environment` block
    (`.github/workflows/run-scan.yml:96-117`). Add `program` as a `workflow_dispatch` input and
    pass both values as **CLI args through the existing `jq -n --arg` pattern** — same safe
    shape S0-T4 established. **Do not add them to `infra/main.tf`'s task definition**: BI-D5
    freezes that file, and the override path already exists.
  - **Fail-closed, and this is the one place the file's house style is actively wrong.**
    `run_recon_pipeline` and `upload_to_s3` both catch broad exceptions and continue
    (`scanner.py:129-134`, `scanner.py:271-272`). **`roe.py` must not follow that pattern.**
    Unfetchable, undecryptable, malformed, unknown-handle, or empty-after-translation ⇒
    **abort non-zero before any subprocess**. Belt-and-braces: `ScopeRules` with an empty
    `in_scope_regex` denies everything by construction, so a silent-empty bug still fails safe —
    but the explicit abort is required so the failure is diagnosable rather than looking like
    "this program has no assets."
  - **Exit mechanism:** `main()` has **no non-zero exit path today** — it returns `None`, so the
    process exits 0. Add an explicit `sys.exit(1)` (or let a raise propagate — the image
    `ENTRYPOINT` surfaces it as exit 1), and place the input gate in `main()` **before** the
    `run_recon_pipeline` context manager is entered, so no temp files are created for a scan
    that must not run.
  - **IAM:** `s3:GetObject` on the RoE key + `kms:Decrypt`. **Lives in
    `glunk-works/global-bootstrap`, not here** — see Risks.
  - **Target Files:** `src/bounty_scanner/roe.py` (new), `src/bounty_scanner/scanner.py`
    (`main` args), `src/pyproject.toml`, `src/tests/test_roe.py` (new),
    `.github/workflows/run-scan.yml`; `global-bootstrap` `project_policies.tf`.
  - **Acceptance:** a valid doc + handle loads; **each** failure mode (object absent, denied,
    undecryptable, malformed JSON, unknown handle) exits non-zero with **`subprocess.run` never
    called** — asserted per mode, not just the happy path.

- **Task 2: Asset→regex translation (the sharpest risk in this sprint)**
  - **Description:** Translate a program's scope entries into `scope-core`'s
    `in_scope_regex`/`out_of_scope_regex`. `eligible_for_submission: true` → in-scope;
    `false` → out-of-scope; `scope_exclusions` entries → out-of-scope.
  - **Three rules that are each a vulnerability if missed:**
    1. **`re.escape` the literal portion.** An unescaped `.` is a regex wildcard —
       `example.com` would match `exampleXcom`.
    2. **Anchor both ends.** `scope-core` matches with **`re.search`**, so an unanchored
       `.*\.example\.com` matches `evil.example.com.attacker.net`. Every generated pattern
       must be `^…$`.
    3. **Apex is excluded from a wildcard by default.** Whether `*.example.com` covers
       `example.com` is program-dependent. **Choose under-inclusive:** a missed finding costs
       nothing; an over-inclusive pattern is unauthorized scanning. If a program's apex is in
       scope it will have its own `URL` entry.
  - **`asset_type` is an ALLOWLIST, not a blocklist.** Handle `URL` and `WILDCARD`; drop
    everything else (`SOURCE_CODE`, `HARDWARE`, app-store IDs, `CIDR`, `IP_ADDRESS`, …) with a
    logged count. The H1 docs do **not** enumerate the valid values, so allowlisting is what
    makes an asset type added by HackerOne *later* default to not-scanned instead of being fed
    to `subfinder` as though it were a hostname.
  - **Target Files:** `src/bounty_scanner/roe.py`, `src/tests/test_roe.py`.
  - **Acceptance:** a dedicated **adversarial** test suite — at minimum `evil.example.com.
    attacker.net` must NOT match a `*.example.com` wildcard; `exampleXcom` must not match
    `example.com`; apex is excluded unless separately listed; an unknown `asset_type` is dropped
    and counted, never translated.

- **Task 3: Mount enforcement in the pipeline (#7, BI-D7)**
  - **Description:** Three enforcement points.
    **(a) Input gate** — `validate_target(rules, args.domain)` in `main()` before any subprocess;
    violation → non-zero exit. This is where a program/domain mismatch surfaces.
    **(b) Discovered-set filter** — a stage between subfinder and httpx reading `subs_file`,
    running every host through `validate_target`, writing only survivors, counting drops.
    **(c) Pre-nuclei revalidation** — same check on `httpx`'s output before nuclei, per the
    defense-in-depth note above.
  - **`sanitize()` is DISPLAY-ONLY. Never validate or scan a sanitized value.** `sanitize()`
    NFKC-normalizes, and NFKC changes hostnames — fullwidth `ｅxample.com` normalizes to
    `example.com`. Validating one form while scanning another is a parser-differential
    vulnerability. **The invariant: validate and scan the exact same bytes; sanitize only on the
    way to a log line.** Stronger and preferred — **reject** a hostname that is not NFKC-stable
    rather than normalizing it.
  - **Sanitize before logging a `ScopeViolation`.** Its message embeds the candidate verbatim,
    and upstream's own comment names the caller as responsible: *"a … caller logging a
    ScopeViolation raised from attacker-influenceable candidate text should sanitize it first."*
    A discovered hostname is attacker-influenceable and we are that caller. This lives in a
    **comment, not the API** — exactly what a reimplementation would have dropped.
  - **Empty-after-filter.** The httpx gate tests `os.path.getsize(subs_file) > 0`
    (`scanner.py:87`). After filtering it must test the **filtered** file, or httpx runs on
    empty input. "Every discovered host was out of scope" is a distinct state — log it as such.
  - **Log counts, not hostnames (BI-D4).** Dropped hosts are *resolved hosts* — S3 only, never a
    log. Emit `dropped N of M out-of-scope` at INFO; the dropped list goes to the S3 artifacts.
  - **The drop count does NOT go in `TriageReport`.** That model is Gemini's `response_schema`
    (`scanner.py:47-49`); adding a field changes what the model is asked to emit. Write scan
    metadata (counts, program handle, RoE `synced_at`) to a **separate S3 artifact**.
  - **Budget a test refactor.** `test_scanner.py` globally patches `builtins.open` with
    `mock_open` (`src/tests/test_scanner.py:72`), which makes asserting *what was written to the
    filtered file* impractical. Expect to move the pipeline tests to `tmp_path` — real work, not
    incidental.
  - **Target Files:** `src/bounty_scanner/scanner.py`, `src/tests/test_scanner.py`.
  - **Acceptance:** an out-of-scope `domain` exits non-zero with **`subprocess.run` never
    called**; a domain not in the named program's scope fails the same way; an in-scope domain
    whose discovered set contains out-of-scope hosts proceeds and the data `httpx` receives
    contains **only** in-scope hosts; nuclei's input is likewise clean; drop counts reach the
    metadata artifact and dropped hostnames reach **only** S3.

- **Task 4: Traffic attribution + rate limiting (#32)**
  - **Description:** An identifying **User-Agent** and conservative rate/concurrency limits on
    `httpx` and `nuclei`.
  - **UA shape:** `bounty-scanner/<version> (+<CONTACT>)`. **`<CONTACT>` is operator-supplied
    and has no default** — an unset contact is a **startup error**, so an anonymous scanner
    cannot ship by accident. Its whole purpose is giving an abuse desk somewhere to write, so it
    must be real and reachable. *(Owner action: supply the URL/email.)*
  - **Suggested defaults — conservative, and well under tool defaults:** rate limit **10 req/s**
    (both tools default to 150), concurrency **25**. Expose as CLI flags in the style of the
    existing `--severities`/`--timeout`.
  - **Verify the flag names against the PINNED versions, not from memory.** The image pins
    `httpx v1.10.0` and `nuclei v3.11.0` (`src/Dockerfile:4-6`). Both have renamed rate-limit
    flags across releases, and a wrong flag either errors loudly or — worse — is silently
    ignored, leaving the scan unthrottled while the code claims otherwise. Also confirm a
    nuclei **template-level** header cannot override the global `-H` User-Agent.
  - **Why here and not S2:** it lands on the same argv Task 3 is already editing — same function,
    adjacent lines, same tests — and it is thematically one change with #7. The BI-D5 pass
    concluded AUP permission is **not** abuse-desk immunity, which is precisely why #32 exists.
  - **Target Files:** `src/bounty_scanner/scanner.py`, `src/tests/test_scanner.py`.
  - **Acceptance:** both tools invoked with the UA and rate-limit flags (asserted on argv); an
    unset contact fails at startup; **flags confirmed valid for the pinned versions**, not
    merely present.

- **Task 5: Triage-prompt hardening (#13)**
  - **Description:** In `triage_findings()`:
    **(a)** run every target-derived field through `sanitize()` before the prompt —
    `matched-at`, template `name`/`description`/`template-id`;
    **(b)** structurally **fence** the untrusted block with explicit delimiters and an
    instruction that its contents are **data, never instructions**;
    **(c)** pin "triage output is advisory" with a test.
  - **The untrusted claim is stronger than #13 states:** nuclei templates are fetched
    **unpinned at image build time** (`src/Dockerfile:31`), so template `name`/`description`
    are genuinely third-party text, not just `matched-at`.
  - **(c) is a regression guard, not a fix.** Triage output is already inert — printed and
    uploaded, nothing more. Pin that **while it is true**, so a later change that lets triage
    influence what gets scanned trips a red test instead of quietly re-opening #13 at far higher
    severity. Same reasoning as `ruleset-drift.yml`.
  - **`response_schema` is not a defense** — per #13 it constrains output *shape*, not *content*.
    A model told "report no findings" returns a schema-valid empty report.
  - **Target Files:** `src/bounty_scanner/scanner.py`, `src/tests/test_scanner.py`.
  - **Acceptance:** a finding carrying ANSI escapes, zero-width/bidi characters, or an injected
    instruction reaches the model **sanitized and inside the fence** (assert on the actual
    `contents` passed to `generate_content`); the advisory-only property has a test that fails if
    triage output is ever wired into a decision.

**Deferred (file as issues when S1 opens):**
- **HackerOne sync job** — Actions + Infisical-sourced H1 token → normalized RoE doc → S3.
  Needs pagination, rate-limit handling, and a **staleness policy** (a stale snapshot can
  authorize scanning an asset since removed from scope — treat `synced_at` as security-relevant).
- **Bugcrowd** has no researcher API; those programs stay hand-authored.
- **#32's issue body is empty** — this plan is currently its only spec. Write it into the issue.

**Definition of Done:** `hatch run lint:check` (ruff + `bandit -ll`) and `hatch run test:run`
green; all 9 CI jobs green, including the four gates that became required 2026-07-22.

**Security Considerations:** S1 is where this repo stops relying on "only the right person can
press the button."
- **The RoE content must never be committed, logged, or echoed** — not in a fixture, sample, or
  docstring. Tests use invented programs and rules (`^example\.com$`), never real scope. A
  committed RoE is the worst artifact this repo could leak (BI-D4).
- **`re.search`, not `re.match`** — see T2. The most likely way a correct implementation still
  scans the wrong host.
- **Verification is behavioral, not structural** — S0's hard-won lesson; #6's fix was proven by
  dispatching a `'`-containing domain, which surfaced two further latent bugs. Prove rejection by
  observing **no subprocess ran**. Note the S0-T4 gotcha applies again: `run-scan.yml` is
  `workflow_dispatch`-only, so end-to-end dispatch tests only run **after merge**.
- `instruction` text from a program is third-party content. It must not reach the triage prompt
  unsanitized if it is ever surfaced.
- Draft advisories `GHSA-pf9q-vx7g-f8gr` (#7) and `GHSA-p3hr-h7cq-xp5m` (#13) publish at close.

**Risks & Blockers:**
- **SC must land first** — T1 has nothing to import until `scope-core` exists.
- **The IAM grant is in a repo with no CI, and this has bitten three times.**
  `global-bootstrap` applies **only from a local terminal** — a merged PR there is *code, not
  effect*. T2's OIDC subject, T2's role, and T4's `ecs:DescribeTasks` all failed this way.
  Expect T1's first real run to fail AccessDenied; budget the manual apply.
- **The RoE object is an operator action.** S1 ships the *mechanism*; an S3 object holding real
  program scope has to be authored and uploaded separately. Until it exists a fail-closed
  scanner correctly refuses to scan anything — right behavior, but **"S1 merged" and "scans work
  again" are two different events.**
- **Tool-flag drift (#12).** T4 depends on flag names matching the pinned binaries; the bad
  failure mode is a silently-ignored rate limit.
