### FILEPATH: /sprints/SC_scope_core_extraction/sprint_plan.md

**Pass Goal:** Extract loop-orchestrator's two security primitives — the structural scope
validator (`tools/scope_validator`) and the ingestion sanitizer (`tools/ingest.sanitize`) —
into a **dedicated shared package repo**, `glunk-works/scope-core`, and re-point
loop-orchestrator at it. This is the prerequisite for **S1**, which mounts those primitives at
the bounty-infra scanner's boundary to close #7/#13. **BI-D6** (this pass) amends BI-D3's
docs-only rule; see the roadmap.

**Why now, and why not later.** loop-orchestrator shipped these primitives with **zero live
consumers on purpose** (its P0-D11: "the deliverable is the primitives only, with no live
consumer" — the Phase-1 scanning MCP tools that mount them are a later sprint). That makes
*right now* the cheapest this extraction will ever be: nothing imports them yet, so re-pointing
is a package rename across their own tests and nothing else. Every sprint we wait, Phase 1 adds
call sites that have to move too.

**This pass is bookkeeping, not design.** The code is already written, already tested, and
already the right shape — see *Why these are safe to share* below. Nothing about the primitives'
semantics changes here. If this pass finds itself redesigning `validate_target`, it has gone
wrong.

**Out of scope:**
- **Any bounty-infra `src/` change.** That is S1. This pass does not touch this repo except for
  the planning record (this file + the roadmap + the cursor).
- **Mounting the primitives at any boundary.** loop-orchestrator's Phase-1 MCP tools and
  bounty-infra's S1 are both *consumers*; this pass only relocates the library.
- **Widening what the primitives do.** No new rules, no new sanitizer passes, no
  reject-vs-escalate policy (loop-orchestrator's P0-D14 deliberately left that to whichever
  consumer issues actions — bounty-infra's answer to it is an **S1** decision, recorded there).
- **The central conventions repo (BI-D3).** Still its own separate pass and still docs-only.
  BI-D6 does **not** merge the two — `scope-core` is a code package with its own release
  cadence, deliberately not co-located with a docs repo.

**Context — the contradiction this resolves.** Two records disagreed, and the bounty-infra one
was wrong:

| Record | Says |
|---|---|
| loop-orchestrator `sprints/45_.../sprint_plan.md` | primitives are "**built once here and shared into the bounty loop**", and are "the concrete fix for `bounty-infra#7`" / "`#13`" |
| bounty-infra BI-D3 + `CLAUDE.md` | "**NOT a shared-code package**… #7 is bounty-infra's own impl" |

BI-D3's clause was written as a **scope-control measure on the conventions repo** — to stop a
docs pass from ballooning into a code-sharing project and blocking S1 — not as a considered
rejection of sharing. Owner overruled it 2026-07-22; recorded as **BI-D6**.

**Why these are safe to share (the three facts that make this tractable):**
1. **Already loader-agnostic.** `ScopeRules.from_target()` accepts a structural `Protocol`
   (`_HasRulesOfEngagement`), *not* a Postgres row — loop-orchestrator's `targets` table and
   bounty-infra's S3-hosted RoE are already both supported callers. **Share the decider, not
   the loader.** No refactor needed to make the code portable; this was designed in.
2. **Tiny and pure.** ~175 lines over three files, `pydantic` + stdlib only, no I/O, no
   credentials, no framework coupling. bounty-infra already depends on pydantic, so the
   dependency delta is zero. This is the shape of code-sharing that does not rot.
3. **Both repos are public, and the sensitive part isn't the code.** The scope *mechanism* is
   publishable; the scope *rules* (which programs the operator is engaged with) stay in
   Infisical/S3 and never enter either repo. A public package leaks nothing.

**The security argument is the real one.** Once loop-orchestrator #18 lands and it dispatches
scans here, two independent implementations of "in scope" means the orchestrator can believe a
target is in-scope that the scanner rejects — or, far worse, the reverse. One definition of a
safety invariant, in one place, is the point. Convenience is secondary.

**Tasks:**

- **Task 1: Stand up `glunk-works/scope-core`**
  - **Description:** New **public** repo holding the three modules and their tests, moved
    verbatim from loop-orchestrator — `rules.py` (`ScopeRules`), `validate.py`
    (`validate_target`, `is_action_banned`, `ScopeViolation`), `sanitize.py` (`sanitize`,
    `DEFAULT_MAX_LEN`). Port the existing tests too: loop-orchestrator has
    `tests/tools/scope_validator/{test_rules,test_validate,test_boundary}.py` and
    `tests/tools/ingest/test_sanitize.py` — **these move with the code**, they are the
    evidence the semantics survived the move. Rewrite only the import paths.
  - **Package layout:** flatten `tools/scope_validator/` + `tools/ingest/` into one
    `scope_core/` package. Keep the module names (`rules`, `validate`, `sanitize`) so the
    diff against loop-orchestrator's history stays readable.
  - **`test_boundary.py` needs re-aiming, not deleting.** It currently pins that
    `scope_validator` carries no runtime import edge onto `tools/inventory_db` (the `Target`
    reference is `TYPE_CHECKING`-only). In `scope-core` that edge is impossible by
    construction, so the guard as written can never fail — a guard that cannot go RED is the
    failure mode loop-orchestrator's own BL-15 warns about. Re-point it at the property that
    still matters and can still break: **`scope_core` imports nothing outside stdlib +
    pydantic.** Verify it goes RED under a planted disallowed import before trusting it.
  - **Governance:** mirror this org's established pattern rather than inventing one — a
    `protected-integration-branches` ruleset (`pull_request` + `deletion` +
    `non_fast_forward`, `bypass_actors: []`, `required_approving_review_count: 0`), CI with
    bare job ids as check contexts, and required checks applied **only after they have
    reported green once**. Do not gold-plate: this repo has no infra, no credentials, and no
    deploy path, so it needs `lint`/`test` and little else at first.
  - **Target Files:** the new repo (all of it).
  - **Acceptance:** `scope-core`'s ported tests pass unmodified in semantics; the
    stdlib+pydantic import guard demonstrably goes RED under a planted import; the ruleset is
    live and its required checks have each reported green once.

- **Task 2: Re-point loop-orchestrator at the package**
  - **Description:** Add the `scope-core` dependency, delete
    `src/loop_orchestrator/tools/scope_validator/` and `src/loop_orchestrator/tools/ingest/`,
    and update every import. Per P0-D11 there are **no live consumers**, so the blast radius is
    that repo's own tests — confirm that with a grep before starting rather than assuming it.
  - **Deleting the local copies is the whole point.** Standing up `scope-core` while
    loop-orchestrator keeps its own copy would *create* the two-divergent-definitions failure
    mode this pass exists to prevent, at the cost of an extra repo. If Task 2 does not land,
    Task 1 is a net negative.
  - **loop-orchestrator's own Definition of Done applies, and it is heavier than this repo's.**
    Its sprint-45 record states that a change touching `src/` requires a **fresh-session
    `architect-review`** (its P0-D16) plus a `/critic-gate` pass. Deleting
    `src/loop_orchestrator/tools/**` is exactly such a change, so budget that review — this
    task is slower than its diff suggests. Read that repo's `CLAUDE.md` before opening the PR
    rather than assuming bounty-infra's bar transfers.
  - **Target Files:** loop-orchestrator `pyproject.toml`, `src/loop_orchestrator/tools/**`,
    `tests/tools/**`, and its `docs/bounty_loop_architecture.md` §5/§10 + sprint-45 record
    (which currently describe the primitives as living there).
  - **Acceptance:** loop-orchestrator's full gate is green with the local copies **deleted**;
    no `scope_validator`/`ingest` module remains under `src/loop_orchestrator/tools/`; its
    architecture doc points at `scope-core`.

**Distribution — recommended, open to veto.** Pin by **commit SHA via a PEP 508 direct
reference**, e.g.
`scope-core @ https://github.com/glunk-works/scope-core/archive/<sha>.tar.gz`, rather than
publishing to PyPI. Rationale:
- It matches this org's demonstrated discipline exactly — every GitHub Action here is
  SHA-pinned for the same reason (a mutable tag is a handoff to whoever moves it).
- **No release infrastructure to build**, which is what keeps this pass short.
- A **tarball URL, not `git+https://`** — **verified, not assumed**: only the Go builder stage
  installs `git` (`src/Dockerfile:3`); the `python:3.14-slim` runtime stage that runs
  `pip install .` (`src/Dockerfile:29`) has no `git` binary. A `git+https://` dependency would
  fail the image build outright. Do not "simplify" the tarball URL to a git URL later.
- **Known consequence:** a project with a direct-reference dependency cannot itself be
  uploaded to PyPI. Neither consumer publishes to PyPI today — bounty-infra's `package` job
  runs `hatch build` for the container image, not for an index — so this costs nothing now.
  **If either repo ever needs to publish, this decision has to be revisited first.**

> **⚠ Smoke-test the mechanism BEFORE committing to it — it can block every merge.**
> `dependency-audit` (pip-audit) and `sbom` (cyclonedx-py) **both scan the installed
> environment**, deliberately not `skip-install` — `src/pyproject.toml` says so in comments.
> A direct-reference dependency that does not exist on PyPI is an unknown to both tools, and
> **both became required checks on 2026-07-22**. If either errors rather than warns, SC lands
> and every subsequent bounty-infra PR is unmergeable. Install the tarball dep into a scratch
> venv and run `pip-audit --skip-editable` + `cyclonedx-py environment` against it **first**.
> If either breaks, fall back to PyPI publication (adds a release workflow to Task 1) rather
> than suppressing the gate.

**Version floors — specify them, do not inherit by accident.** `scope-core` uses pydantic-v2-only
APIs (`model_validator(mode="after")`, `ConfigDict`, `PrivateAttr`) and PEP 585/604 syntax under
`from __future__ import annotations`. Consumers: bounty-infra declares
`requires-python = ">=3.11"` with `pydantic>=2.0.0` and a **3.14** runtime image, while its CI
validates on 3.11 (the known #16 drift). Declare a floor that satisfies both consumers and is
tested at both ends of that range, or the shared package becomes the thing that breaks an
install nobody changed.

**Security Considerations:** This pass moves security-critical code without changing it, so the
dominant risk is **silent semantic drift during the move** — a subtly different regex mode, a
lost fail-closed branch, a dropped sanitizer pass. Mitigation is that the tests move with the
code and must pass unmodified in behavior. Two semantics worth restating because they are easy
to "clean up" into a vulnerability:
- **`validate_target` is fail-closed and deny-wins:** allowed iff ≥1 in-scope match **and** 0
  out-of-scope matches; an out-of-scope match always vetoes; an **empty `in_scope_regex` denies
  everything**. Never "fix" the empty case to mean allow-all.
- **Patterns use `re.search`, not `re.match`** — unanchored by design, so `example\.com` also
  matches `example.com.attacker.net`. This is documented upstream and callers are expected to
  anchor (`^example\.com$`) in their RoE. Do not silently anchor patterns during the move; that
  changes every existing rule's meaning.

The new repo holds **no secrets and no credentials** and is safe to be public: it is the
mechanism, never the rules.

**Risks & Blockers:**
- **This pass blocks S1.** S1 Task 1 is "add the dependency," so SC has to land first. If SC
  stalls, S1 stalls — that is the accepted cost of the owner's chosen sequencing, taken because
  the alternative (S1 spanning three repos) is worse.
- **A third repo is a real ongoing cost** — another ruleset, another CI config, another thing
  that can drift. Accepted deliberately: the alternative is two divergent implementations of
  the invariant that decides whether we are lawfully allowed to touch a host.
- **loop-orchestrator is mid-flight.** Confirm no in-progress sprint there is editing the two
  packages before deleting them, or Task 2 collides with live work.
