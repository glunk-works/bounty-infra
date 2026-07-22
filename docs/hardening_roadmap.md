# bounty-infra — hardening & working-method roadmap (reference of record)

> Established 2026-07-21 from the loop-orchestrator side (Opus/architect planning pass).
> This retrofits loop-orchestrator's disciplined working method onto this pre-existing repo
> **and** remediates the 2026-07-19 security review findings (#6–#14). It is the analog of
> loop-orchestrator's `docs/migration_roadmap.md` for this repo.

## Posture

**Governance-first, then scanner fixes, method interleaved** (locked, micro-gate 1). Branch
protection + a plan gate is the prerequisite for gating everything after it — you cannot
safely merge security fixes through the very ungated path (#8/#9) that is itself a finding.

## Public-repo posture (BI-D4)

**This repository is intentionally public** (portfolio project). Nothing below is a reason to
make it private; it is the set of invariants that make "public" safe. Verified 2026-07-21:
`.tf`/`.yml`/`.py`/`.toml`/`.md` contain **no** account IDs, ARNs, bucket names, or identity
IDs — every account-specific value resolves at runtime through Infisical (`env.TF_STATE_BUCKET`,
`env.AWS_OIDC_ROLE_ARN`, `vars.IDENTITY_ID`) or tofu variables. The only committed literal is
the ECR repo name `glunk-works/bounty-scanner`, which is inert.

**Where each class of sensitive material lives:**

| Class | Home | Never |
|---|---|---|
| Genuine secrets, account-specific values | Infisical (`/bounty-infra`, `prod`) | Committed, or echoed to a workflow log |
| RoE / scope allowlist (S1, #7) | **S3 under the existing KMS key**, fetched by the scanner at startup; Infisical holds only the `s3://…` **pointer** (BI-D8, 2026-07-22 — supersedes "Infisical, runtime config") | A committed `scope.yaml`. It enumerates which bounty programs the operator is engaged with — the most sensitive artifact the system will hold. Also never a workflow log, artifact, or the ECS `containerOverrides` JSON — under BI-D8 the rules never transit CI at all. Test fixtures use invented rules (`^example\.com$`), never real program scope |
| Scan findings, triage reports, resolved hosts/subdomains | S3 only | A workflow log, artifact, or PR comment. This is third-party vulnerability data |
| Pre-remediation vulnerability detail | Draft security advisories (below) | A public issue body, until the fix has landed |

**`tofu plan` output is summarized, never dumped.** Plan renders the account ID, real bucket
names, subnet/SG IDs, and ARNs at runtime even though none are committed. On a **public** repo,
workflow artifacts are world-readable, so "post an artifact instead of a PR comment" is **not**
a mitigation — both disclose. S0-T2 emits change counts + resource addresses only.

**Fork PRs receive no secrets**, so a required `tofu plan` check can never go green for an
outside contributor. Accepted (no external contributors expected). **`pull_request_target` must
stay off the table** as the "fix" — it would hand repo-scoped credentials to fork-controlled code.

**Coordinated disclosure.** Findings #6–#14 were filed as public issues while still unpatched.
Full pre-remediation detail now also lives in **private draft advisories** — `GHSA-59j8-c4rc-2jf4`
(#6), `GHSA-pf9q-vx7g-f8gr` (#7), `GHSA-p3hr-h7cq-xp5m` (#13) — to be **published once the
corresponding sprint closes**. Publishing the analysis *after* remediation is better portfolio
material than the current state, because it demonstrates the timing was understood.

**No private mirror repo.** Each candidate has a better-fitting home than a second repo (table
above); a mirror buys split history and a sync burden, and none of the four classes wants to
live in git. Revisit only if engagement contracts or program NDAs need a document home.

**Wrap + harden, not wrap-only:** loop-orchestrator's bounty loop enforces scope/sanitization
at *its* boundary, but that protects loop-mediated runs only. This scanner is independently
dispatchable, so #7 (scope) and #13 (triage injection) are fixed **here**, not delegated to
the wrapper (loop-orchestrator S47-D12; comments on #7/#13).

## Sprint sequence

| Sprint | Closes | Scope |
|---|---|---|
| **S0 — Governance & CI/CD hardening** | #6, #8, #9, #10 | Branch-protection ruleset + minimal working method; gated OpenTofu deploy (plan-on-PR + apply-on-merge, `production` Environment approval); non-bypassable CI on all paths; `run-scan.yml` injection fix + drop unused `GITHUB_TOKEN`. **Also unblocks loop-orchestrator S47's #18** (same file as #6). |
| **SC — `scope-core` extraction** (BI-D6) | new | **Prerequisite for S1.** Extract loop-orchestrator's scope validator + ingestion sanitizer into `glunk-works/scope-core` and re-point loop-orchestrator at it (deleting its local copies). Cross-repo; touches no bounty-infra `src/`. Cheapest now — those primitives still have zero live consumers. `sprints/SC_scope_core_extraction/sprint_plan.md`. |
| **S1 — Scanner security core** | #7, #13, **#32** | Structural scope check **consumed from `scope-core`** (BI-D6), enforced at **three** points — input gate, discovered-set filter, pre-nuclei revalidation (BI-D7) — over a HackerOne-vocabulary RoE fetched from S3 (BI-D8/D9); triage-prompt hardening (fence + sanitize target-derived fields; triage advisory-only); scanner traffic attribution + rate limiting. **#32 joins S1** — it lands on the same `run_recon_pipeline` argv the scope filter is inserted into, and is thematically one change with #7. Planned 2026-07-22: `sprints/S1_scanner_security_core/sprint_plan.md`. |
| **S2 — Scanner robustness** | #11, #12, #14 | Tighten task-role IAM to what's used; pin tools/templates/deps (reproducible builds); distinguish partial/failed scans from clean success. **#11 is re-scoped by BI-D5** — the Fargate task role it targets is being retired; re-point at the replacement credential path. |
| **SG — CI gate expansion** | new | Adopt the four shared gates (`secrets-scan`/gitleaks, `dependency-audit`, `sbom`, `pr-title`) + **`zizmor`** (workflow security — detects the template-injection class that was #6, converting T4's fix from done-once into can't-regress) + container image scan (trivy/grype) + IaC security scan (checkov/trivy-config; `tflint` lints, it does not scan). |
| **SE — Egress migration (BI-D5)** | new | Retire ECS/VPC/ECR from `infra/**`; per-scan ephemeral VM on Vultr with a reserved IP; re-point `run-scan.yml` at the new launcher; credential path for S3 write; provider abuse-team notification. |

**#6 severity is anticipatory, not live (qualifier added 2026-07-21).** `workflow_dispatch`
requires repo **write** access and there is a single collaborator, so #6 is not currently an
external privilege-boundary crossing — a principal who can dispatch could equally commit a
malicious workflow. It becomes genuinely High the moment **#18** lands and makes the workflow
machine-dispatchable from loop-orchestrator, at which point `target_domain` stops being
operator-typed. This does **not** change the ordering (#6 still ships before #18) but it does
mean S0 is not firefighting. *(`sprints/S0_governance_hardening/sprint_plan.md` still describes
this as "a live RCE-with-AWS-creds surface" — overstated on current facts; amend when S0 opens.)*

Method (skills, an IaC/AWS/Actions `security-critic` agent, the fresh-session
`architect-review` CI gate) layers across S0–S2 — not a dedicated sprint (MG1).

**Ordering after S0 (BI-D5 changes this).** **SG splits along substrate dependence.** Five of
its seven gates — `secrets-scan`, `dependency-audit`, `sbom`, `pr-title`, `zizmor` — touch
neither `infra/**` nor the runtime, so they can land **immediately and in parallel** with
anything else. The remaining two should follow **SE**: an IaC security scan run now would spend
its findings on ECS/VPC resources BI-D5 deletes, and the image scan wants to target whatever
registry SE settles on. **SE before S2**, since S2's #11 targets a role SE retires. **S1 is
independent of both** and can be sequenced on its own merits — but as of 2026-07-22 it has a
prerequisite of its own: **SC before S1** (BI-D6), since S1's first task is "add the
`scope-core` dependency."

## The central conventions repo (BI-D3)

A **new central repo** is the single source of truth for the **working method / Global
Conventions** — the "our way of working" docs that each repo's `CLAUDE.md` **references**,
with **local extensions** per repo. This is a **docs/conventions** central home, **not** a
shared-code package:
- The portable Global Conventions (Python / IaC / commit taxonomy / Definition of Done) live
  in the central repo; loop-orchestrator's `conventions.md` moves/mirrors there too.
- Each repo's `CLAUDE.md` references the central conventions **and adds a local section**
  (bounty-infra: OpenTofu / Actions-security / scanner DoD).
- **Explicitly NOT in scope:** sharing *code* (`scope_validator`, `ingest.sanitize`) as a
  package — #7's scope check is the scanner's **own** implementation (S1). No cross-repo code
  refactor is implied.
- **Lightweight** (stand up a repo, host the conventions, point both `CLAUDE.md` files at it)
  and **does not block or feed S1**. **S0 does not depend on it** — S0's `CLAUDE.md` references
  loop-orchestrator's `conventions.md` as the interim source and points at the central repo
  once it exists.

## RESOLVED — compute-model architecture decision (pass held 2026-07-21; see BI-D5)

**Outcome: scan egress leaves AWS. AWS keeps the control plane.** The scanner runs as an
**ephemeral VM provisioned per scan** on **Vultr** (DigitalOcean as documented fallback),
booted from the existing Docker image, writing to the same S3 findings bucket. Full statement
and rejected alternatives: **BI-D5** below.

### The question was mis-framed as Fargate-vs-Ansible

The original framing (Option A stay Fargate / Option B Ansible VMs / Option C hybrid) treated
this as a **compute** decision. It is not. Compute was never the problem:
`subfinder`/`httpx`/`nuclei` are pure userspace TCP, 1 vCPU / 2 GB is adequate, and Fargate at
~$0.05/hr makes a 30-minute scan cost ~2.5¢ — **cheaper** than an always-on VPS at this run
frequency. The binding constraints are **network identity** and **blast radius**.

### The three findings that decided it

1. **AWS's penetration-testing policy does not cover this workload.** It scopes authorization
   to *"security controls amongst **your AWS assets**"* — third-party bounty targets fall
   entirely outside it, with no researcher carve-out. Scan traffic has never been authorized
   under that policy. <https://aws.amazon.com/security/penetration-testing/>
2. **The egress IP rotates and is unregistrable.** `infra/main.tf` sets
   `map_public_ip_on_launch = true` with no NAT/EIP, so every task presents a different
   AWS-owned address. Two consequences: bounty programs requiring source-IP registration or
   deconfliction cannot be satisfied, and AWS ranges are broadly WAF/CDN-blocked — which
   produces **silent false negatives**, the worst possible failure mode for a pipeline whose
   entire output is "what did we find."
3. **Fargate cannot be fixed in place.** `linuxParameters.capabilities.add` accepts **only
   `SYS_PTRACE`** on Fargate — `NET_ADMIN` and `NET_RAW` are unavailable. This rules out
   SYN-scanning tools permanently, **and** rules out the obvious workaround of tunnelling
   egress through WireGuard for a stable IP (needs `NET_ADMIN` + `/dev/net/tun`). Not awkward
   — structurally impossible.
   <https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_LinuxParameters.html>

**Blast radius is what makes (1) urgent rather than academic.** The AWS account also holds the
OpenTofu state bucket, the findings bucket, and **every GitHub OIDC role for all `glunk-works`
projects** (`global-bootstrap` generates them from `var.projects`). An abuse suspension takes
out the shared foundation, not just this project.

### Provider selection is not a commodity swap

"Use a smaller provider, they're more permissive" is **false as a generalization** — several
budget hosts are markedly *less* tolerant than AWS. The real variable is whether the AUP
prohibits **unauthorized** scanning or **all** scanning. Verified by reading the text:

| Provider | Language | Verdict |
|---|---|---|
| **Vultr** | port scanning permitted *"if explicitly authorized by the destination host and/or network"* | **Chosen** — affirmative permission, conditioned on exactly what a program's RoE grants |
| DigitalOcean | prohibits probing *"without permission"*; silent on authorized third-party testing | Documented fallback — absence of prohibition, not presence of permission |
| AWS | authorization scoped to *"your AWS assets"* | Affirmatively excludes this use case |
| **Hetzner** | prohibits port scanning **and** *"scanning of foreign networks or foreign IP addresses"* | **Disqualified** — the default cheap-VPS pick explicitly bans the reason we would move |

**AUP text and abuse-desk behaviour are separate risks.** Contractual permission does not stop
an automated complaint from suspending a box; it only means the appeal is winnable. Hence the
procedural controls in BI-D5.

### Consequences for the existing sprints

- **S2's #11 (tighten task-role IAM) largely evaporates** — `aws_iam_role.task_role` and
  `execution_role` are Fargate constructs BI-D5 retires. Re-scope #11 to the *replacement*
  credential path (short-lived S3-write creds delivered to the VM) when S3 lands.
- **S1 is unaffected.** #7 (scope enforcement) and #13 (prompt injection) are scanner-internal
  and provider-agnostic — they survive the substrate change intact.
- **T3(d)'s image-rollout mechanism is replaced, its principle is not.** Sha-pinned, CI-gated,
  never `:latest` carries over to whatever registry the VM pulls from.

*(Docs-drift symptom still outstanding: the README lists a `build-and-push.yml` that does not
exist and claims "least privilege IAM" that #11 contradicts — fold into a docs pass.)*

## Locked decisions (this planning pass, 2026-07-21, owner-confirmed via micro-gates)

- **BI-D1 (MG1)** — governance-first sequence (above). (Rejected: full-method-first — delays
  the High vulns; vulns-only — doesn't establish the working method.)
- **BI-D2 (MG2)** — gated deploy: `tofu plan` on PRs touching `infra/**` (visible), apply job
  on merge-to-main targeting a protected `production` **Environment** with a required
  reviewer; `-auto-approve` stays but runs only post-approval. (Rejected: no Environment gate;
  manual-dispatch-only apply.)
- **BI-D3 (MG3, 2026-07-21) — a central repo hosts the shared conventions/way-of-working**
  that each repo's `CLAUDE.md` **references + locally extends** (best long-term home for the
  method). This is the reference-and-extend model with the shared source in a **dedicated
  central repo** rather than in loop-orchestrator. ~~Docs/conventions only — NOT a shared-code
  package~~ — **the no-shared-code clause is SUPERSEDED by BI-D6 (2026-07-22)**; the rest of
  BI-D3 stands, and the conventions repo itself remains **docs-only** (`scope-core` is a
  separate repo with its own release cadence, deliberately not co-located with docs).
  (Rejected: shared source living in loop-orchestrator's own repo — a dedicated central home
  is cleaner long-term.)
- **BI-D4 (2026-07-21) — public-repo posture** (§ *Public-repo posture* above): the repo stays
  **public**; secrets and the RoE allowlist live in **Infisical**, findings in **S3**,
  pre-remediation vuln detail in **draft advisories** published post-fix; `tofu plan` output is
  summarized only. (Rejected: making the repo private — it is deliberate portfolio material;
  a **private mirror repo** for the sensitive elements — every candidate has a better home than
  git, and a mirror adds split history + sync burden.)
- **BI-D5 (2026-07-21) — compute model: scan egress leaves AWS; AWS keeps the control plane.**
  (§ *RESOLVED — compute-model architecture decision* above.) The scanner runs as an
  **ephemeral VM provisioned per scan** on **Vultr** (DigitalOcean documented fallback), booted
  from the existing Docker image, destroyed after the run. **AWS retains** the S3 findings
  bucket + KMS key, the OpenTofu state backend, and the GitHub OIDC roles — none of which carry
  abuse risk, and all of which S0 already hardened. **AWS loses** the ECS cluster, task
  definition, ECR repo, VPC/subnet/SG/IGW, and both Fargate IAM roles.
  - **Ephemerality is the virtue worth keeping, not AWS.** A persistent VPS was rejected
    precisely because it regresses the zero-ingress principle (`infra/main.tf` § *NETWORK
    (Zero-Trust Ingress)*): it needs SSH ingress, patching, and turns cattle into a pet.
    Cloud-init plus the existing image gives the cattle-shaped version.
  - **A reserved/floating IP attaches at boot**, so a registrable, stable source identity and
    per-scan ephemerality are **not** in tension.
  - **The scanner image needs no changes.** `scanner.py` already uses boto3's default
    credential chain and takes everything else via argv — the provider coupling really is only
    the launcher and the credential path. That is the evidence the seam is drawn correctly.
  - **Required procedural controls** (AUP permission ≠ abuse-desk immunity): reserved IP
    registered with each program; proactive notification to the provider's abuse team with
    scope; RoE/authorization documentation kept retrievable.
  - **Rejected:** *Option A, stay Fargate* — AWS's pentest policy affirmatively excludes
    third-party targets, and the rotating IP causes silent false negatives. *Option B, Ansible
    VM nodes* — right instinct (leave Fargate), wrong shape: Ansible provisions pets, and the
    described Amass/ffuf toolset is a separate question from where egress originates.
    *Fargate + NAT/EIP* — fixes the IP, fixes neither the AUP posture nor blast radius.
    *Dedicated scanning AWS account* — fixes blast radius only, knowingly operating outside
    AWS's policy. *Fargate + userspace proxy on a VPS* — viable and minimal, but per-tool proxy
    config with AWS-side DNS is a weaker guarantee than moving the host; only worth it under
    time pressure, and the pipeline is pre-production.

## Locked decisions (S1 planning pass, 2026-07-22, owner-confirmed via micro-gates)

- **BI-D6 (2026-07-22) — shared code IS allowed, via a dedicated small package repo.**
  Supersedes BI-D3's "NOT a shared-code package" clause. loop-orchestrator's two security
  primitives — the structural scope validator and the ingestion sanitizer — move to
  **`glunk-works/scope-core`**, which both repos depend on; **neither product repo depends on
  the other**. Detail and the extraction plan: `sprints/SC_scope_core_extraction/sprint_plan.md`.
  - **The record was self-contradictory and BI-D3 was the wrong half.** loop-orchestrator's
    sprint-45 plan describes these primitives as "**built once here and shared into the bounty
    loop**" and as "the concrete fix for `bounty-infra#7`/`#13`", while BI-D3 said bounty-infra
    must write its own. BI-D3's clause was **scope control on the conventions repo** — stopping
    a docs pass from ballooning into a code-sharing project — not a considered rejection of
    sharing.
  - **Three facts make it tractable:** the primitives are already **loader-agnostic**
    (`ScopeRules.from_target()` takes a structural `Protocol`, not a DB row — so a Postgres
    `targets` table and an S3-hosted RoE are both already supported callers: **share the
    decider, not the loader**); the surface is **~175 lines, pydantic + stdlib, no I/O and no
    credentials**, and bounty-infra already has pydantic, so the dependency delta is zero; and
    **both repos are public while the sensitive part is the rules, not the mechanism** — the
    code publishes safely, the RoE never enters either repo.
  - **The argument is safety, not convenience.** Once loop-orchestrator #18 lands and it
    dispatches scans here, two implementations of "in scope" means the orchestrator can believe
    a target is in-scope that the scanner rejects — or, worse, the reverse.
  - **Timing:** loop-orchestrator shipped these with **zero live consumers by design** (its
    P0-D11), so this is the cheapest extraction will ever be. **Extraction must delete
    loop-orchestrator's local copies**, or it creates the divergence it exists to prevent.
  - (Rejected: *bounty-infra imports loop-orchestrator directly* — wrong dependency direction,
    the scan substrate depending on its own dispatcher, and it drags LangGraph/MCP/Postgres into
    a minimal scanner container. *Fold the code into the BI-D3 conventions repo* — couples a
    docs cadence to a security-primitive release cadence. *Vendor + CI drift guard* — ships
    fastest and matches the `ruleset-drift.yml` idiom, but still leaves two copies and two PRs
    per fix.)
- **BI-D7 (2026-07-22) — split out-of-scope policy: hard-fail the input, filter the discovered
  set.** The dispatched `target_domain` is an **assertion of authority**; if false it is an
  operator/orchestrator error and hard-fails **before any subprocess runs**. A subfinder-
  discovered host is an **observation**; out-of-scope ones are dropped, counted, and the scan
  continues. Nothing out-of-scope reaches `httpx` or `nuclei` either way. This answers
  loop-orchestrator's P0-D14, which deliberately left reject-vs-escalate policy to the consumer.
  - **Validating only the input does not close #7** — `subfinder` enumerates from CT logs and
    passive DNS, which routinely return shared-CDN hosts, vendor subdomains, and third-party-
    owned hosts. The check must be a **filter over the discovered set**, not a gate on argv.
  - (Rejected: *hard-fail everywhere* — one stray CDN hostname kills a valid scan, and a control
    people are motivated to disable is not a control. *Filter everywhere* — a misdispatched
    target yields a clean-looking empty report, the "green for the wrong reason" class S0 spent
    a sprint eliminating.)
- **BI-D8 (2026-07-22) — the scanner fetches its RoE from S3 at startup; Infisical holds only
  the pointer.** Rules live in **S3 under the existing KMS key**, fetched with the credentials
  the scanner already needs for findings upload. The RoE therefore **never transits GitHub
  Actions** — no log, artifact, PR comment, or ECS `containerOverrides` JSON — and it survives
  BI-D5, since S3 + KMS are exactly what AWS retains. Load is **fail-closed**: unfetchable,
  undecryptable, or malformed rules abort the run before any subprocess.
  - **Why not Infisical directly from the scanner:** that parks a secrets-manager credential on
    the **scan VM** — by BI-D5's own design the most exposed and most disposable machine in the
    system, and the one most likely to be seized or abuse-suspended.
  - (Rejected: *env var carrying the rules* — transits CI and lands readable via
    `aws ecs describe-task-definition`. *`--scope-file` + launcher materializes it* — clean
    scanner-side seam, but on Fargate the file still arrives via env-then-write, inheriting the
    same exposure and adding a layer.)
  - **Scope correction (2026-07-22):** "S1 survives BI-D5 untouched" holds for the **scanner
    code**, not the credential path. The `s3:GetObject`/`kms:Decrypt` grant attaches to a
    Fargate task role BI-D5 **retires**, so SE re-points it. Do not read BI-D8 as substrate-free.
- **BI-D9 (2026-07-22) — the RoE document: HackerOne's vocabulary, our normalized schema,
  program-keyed, with explicit program selection.** The operator runs programs on **HackerOne
  and Bugcrowd**; only HackerOne has a researcher-facing API. Bugcrowd programs are therefore
  hand-authored and share the same document, so the schema adopts H1's **vocabulary**
  (`asset_type`, `asset_identifier`, `eligible_for_submission`) **without coupling to its API
  envelope** — a vendor shape no second platform will ever match. Format is **JSON**, not YAML
  (YAML means adding PyYAML, a new supply-chain dependency while #12 is open).
  - **Explicit program selection, never search-all.** `run-scan.yml` gains a required `program`
    input; the scanner validates `target_domain` against **that program's rules only**. Two
    programs matching one domain is ambiguous, and a typo would silently borrow a different
    program's authorization. This strengthens BI-D7: the dispatcher asserts *both* "this
    program" and "this domain," and a **mismatch between them hard-fails** — the most likely
    real-world operator error S1 can catch.
  - **Two independent out-of-scope sources, verified against the live API 2026-07-22:**
    `structured_scopes` entries with `eligible_for_submission: false`, **and** a separate
    `GET /hackers/programs/{handle}/scope_exclusions` endpoint. Both must map to
    `out_of_scope_regex`; missing the second means scanning explicitly-excluded assets while
    believing we are compliant.
  - **`asset_type` is an allowlist** (`URL`, `WILDCARD`), not a blocklist. H1 does not publish an
    enumerated list, so allowlisting makes any type added later default to **not scanned**
    rather than being fed to `subfinder` as if it were a hostname. CIDR/IP assets are excluded —
    `scope-core` decides on regexes and this pipeline is domain-driven.
  - **Wildcard translation is the sharpest risk in S1**: `re.escape` the literal part, **anchor
    both ends** (`scope-core` uses `re.search`, so unanchored patterns match
    `evil.example.com.attacker.net`), and treat the **apex as excluded by default** — a missed
    finding costs nothing, an over-inclusive pattern is unauthorized scanning.
  - **The H1 token never reaches the scan VM.** It is consumed only by the (deferred) sync job
    in Actions with an Infisical-sourced credential — same argument that rejected
    Infisical-on-VM in BI-D8. **S1 ships enforcement against a hand-authored document**;
    automating the pull is a follow-on task, so the schema is validated by hand against a real
    program before any sync code is written against it.
  - **Per-program `identification` block** (optional: `ua_suffix`, `headers`) extends the global
    User-Agent for one program, since programs sometimes mandate a specific marker and H1
    surfaces that in the structured-scope `instruction` field. Keeps such a requirement an **RoE
    edit, not a code change**. `instruction` is third-party text and is **transcribed by an
    operator, never auto-parsed into headers**.
  - **The UA is platform-neutral and never leads with a platform brand.** `HackerOne-Research-…`
    was proposed and rejected: a platform name in the product-token position implies the traffic
    originates from **HackerOne Inc.**, which creates a problem with the platform if a target
    complains about traffic branded as theirs, and is simply wrong when the selected program is a
    Bugcrowd one. Identify *with* a platform via a resolvable contact URL; never *as* one.
    Locked: `bounty-scanner/<version> (+https://hackerone.com/seuss)` — RFC 9110 product token
    plus the established `+URL` bot convention, contact being the operator's H1 profile
    (self-authenticating; shows a receiving SOC this is a real researcher). `<version>` is read
    from **package metadata**, never hardcoded — a UA claiming a version the build isn't is worse
    than none. **An unset contact remains a startup error**, so an anonymous scanner cannot ship
    by accident.

## Cross-repo coupling

- **loop-orchestrator #18** (recon dispatch contract) lands `seed`/`token` inputs in
  `run-scan.yml` — **must ride S0's #6 fix** (env+jq, no inline `${{ }}`). So S0 unblocks
  S47's live V-run.
- **kms:Decrypt:** #11 tightens the *scanner task role*; loop-orchestrator's fetch uses a
  *different* OIDC role that needs its own `kms:Decrypt` — no conflict (distinct principals).

## Pointers

- The 2026-07-19 review findings: issues #6–#16 (this repo).
- loop-orchestrator `docs/bounty_loop_architecture.md` §5/§10, S47-D12 — shared design context.
- `sprints/S0_governance_hardening/sprint_plan.md` — the detailed S0 plan.
