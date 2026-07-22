"""RoE (rules-of-engagement) loading and scope translation (S1 Tasks 1/2).

Fail-closed throughout, deliberately NOT following scanner.py's
except-and-continue house style (BI-D8): every failure mode here --
object absent, access denied, undecryptable, malformed JSON, handle
mismatch, empty-after-translation -- raises `RoEError`. The caller
(`scanner.main`) must let that abort the process before any subprocess
runs.

Layout: one RoE object PER ENGAGEMENT, `s3://<bucket>/roe/<program>/scope.json`
(BI-D9 revision, 2026-07-22) -- not one shared document keyed by program.
A bad hand-edit to one engagement's file can't deny scans for every other
engagement, and there is no in-repo "list every program" affordance to
search across, which structurally reinforces BI-D9's "never search all
programs" rule rather than merely relying on this module's callers to
respect it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, ValidationError
from scope_core import ScopeRules

logger = logging.getLogger(__name__)

# HackerOne structured-scope asset_type ALLOWLIST (S1 Task 2). Only these
# translate to a regex pattern; every other value -- SOURCE_CODE, HARDWARE,
# app-store IDs, CIDR, IP_ADDRESS, and anything HackerOne adds later --
# is dropped and counted, never fed to subfinder as though it were a
# hostname. An allowlist, not a blocklist, is what makes an unrecognized
# future asset_type default to not-scanned.
_ALLOWED_ASSET_TYPES = frozenset({"URL", "WILDCARD"})

# `--program` now participates in an S3 key (`roe/<program>/scope.json`),
# not just a dict lookup -- constrain it to a conservative handle shape
# before it touches a path. S3 itself has no directory-traversal semantics
# (a literal ".." segment is just a character in a flat key namespace), but
# a malformed handle producing a weird literal key is still worth rejecting
# outright rather than tolerating.
_PROGRAM_HANDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class RoEError(Exception):
    """Any RoE load/select/translate failure. Always fatal -- see module
    docstring."""


class ScopeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type: str
    asset_identifier: str
    eligible_for_submission: bool = True


class Identification(BaseModel):
    """Per-program User-Agent/header override (BI-D9). Optional; falls
    back to the global default (S1 Task 4) when absent for a program."""

    model_config = ConfigDict(extra="forbid")

    ua_suffix: str | None = None
    headers: dict[str, str] = {}


class Program(BaseModel):
    """One engagement's RoE. This IS the top-level document at
    `roe/<handle>/scope.json` -- no wrapping map, since the S3 key is
    already the selector."""

    model_config = ConfigDict(extra="forbid")

    version: int
    platform: str
    handle: str
    synced_at: str
    scopes: list[ScopeEntry] = []
    # Second out-of-scope source (BI-D9), distinct from
    # `eligible_for_submission: false` -- HackerOne's structured-scope API
    # exposes explicit exclusions via its own endpoint. Both must land in
    # out_of_scope_regex or a scan could touch an explicitly-excluded asset
    # while believing it was compliant.
    scope_exclusions: list[ScopeEntry] = []
    identification: Identification | None = None


@dataclass(frozen=True)
class ProgramScope:
    """What `main()` needs to enforce scope and identify itself for one
    scan run."""

    rules: ScopeRules
    program_handle: str
    platform: str
    synced_at: str
    identification: Identification | None
    dropped_unknown_asset_type: int = 0


def validate_program_handle(program_handle: str) -> None:
    if not _PROGRAM_HANDLE_RE.match(program_handle):
        raise RoEError(
            f"--program {program_handle!r} is not a valid handle "
            "(expected alphanumeric, '-', '_' only)"
        )


def scope_uri_for_program(bucket: str, program_handle: str) -> str:
    """The default per-engagement layout: `roe/<program>/scope.json` under
    the same findings bucket the task role already reads/writes (BI-D8:
    reuse the existing S3 + KMS grant, no new IAM anywhere)."""
    return f"s3://{bucket}/roe/{program_handle}/scope.json"


def load_roe(scope_uri: str, expected_handle: str) -> Program:
    """Fetch and parse one engagement's RoE object from S3. S3 performs KMS
    decryption server-side (given `s3:GetObject` + `kms:Decrypt` on the
    caller's role -- already granted on the findings bucket, see BI-D8);
    this function does no manual decrypt call.

    `expected_handle` must match the loaded document's own `handle` field --
    a self-consistency check only meaningful now that the S3 key itself is
    the selector: a misnamed prefix or a copy-pasted file would otherwise
    silently apply the wrong engagement's rules under the right-looking key.
    """
    if not scope_uri.startswith("s3://"):
        raise RoEError(f"--scope-uri must be an s3://bucket/key URI, got {scope_uri!r}")
    bucket, _, key = scope_uri[len("s3://") :].partition("/")
    if not bucket or not key:
        raise RoEError(f"--scope-uri must be an s3://bucket/key URI, got {scope_uri!r}")

    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
    except ClientError as exc:
        raise RoEError(
            f"could not fetch RoE object s3://{bucket}/{key}: {exc}"
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RoEError(
            f"RoE object s3://{bucket}/{key} is not valid JSON: {exc}"
        ) from exc

    try:
        program = Program.model_validate(payload)
    except ValidationError as exc:
        raise RoEError(
            f"RoE object s3://{bucket}/{key} does not match the expected schema: {exc}"
        ) from exc

    if program.handle != expected_handle:
        raise RoEError(
            f"RoE object s3://{bucket}/{key} declares handle {program.handle!r}, "
            f"expected {expected_handle!r} -- refusing to scan"
        )

    return program


def _hostname_pattern(identifier: str) -> str:
    """re.escape the literal, anchor both ends (S1 Task 2 rule 1/2):
    scope-core matches via `re.search`, so an unanchored or unescaped
    pattern is a scope hole -- `example.com` unescaped would match
    `exampleXcom`; unanchored, `example\\.com` would match
    `example.com.attacker.net`.
    """
    return f"^{re.escape(identifier)}$"


def _wildcard_pattern(identifier: str) -> str:
    """Translate a HackerOne WILDCARD asset_identifier ('*.example.com')
    into an anchored regex covering any subdomain, apex EXCLUDED by
    construction (S1 Task 2 rule 3): whether `*.example.com` covers
    `example.com` is program-dependent, and an over-inclusive pattern is
    unauthorized scanning, so under-inclusive is the safe default. A
    program whose apex is in scope lists it as its own URL entry.

    `^.+<escaped-suffix>$` cannot match the bare apex (the apex string is
    shorter than the escaped suffix it would have to end with), and the
    escaped, anchored suffix rejects both `evil.example.com.attacker.net`
    (wrong tail) and `notexample.com` (no literal dot before the label).
    """
    if not identifier.startswith("*."):
        # Not actually wildcard-shaped -- treat as a literal host rather
        # than silently widening a malformed entry into "match anything".
        return _hostname_pattern(identifier)
    suffix = identifier[1:]  # ".example.com"
    return f"^.+{re.escape(suffix)}$"


def _translate_scope_entry(entry: ScopeEntry) -> str | None:
    """Return the anchored regex pattern for one scope entry, or None if
    `asset_type` is not in the allowlist."""
    if entry.asset_type not in _ALLOWED_ASSET_TYPES:
        return None
    if entry.asset_type == "WILDCARD":
        return _wildcard_pattern(entry.asset_identifier)
    return _hostname_pattern(entry.asset_identifier)


def translate_program_scope(program: Program) -> tuple[ScopeRules, int]:
    """S1 Task 2: `eligible_for_submission: true` -> in-scope; `false` ->
    out-of-scope; every `scope_exclusions` entry -> out-of-scope
    unconditionally. Returns the translated rules and a count of entries
    dropped for an unrecognized `asset_type` (logged as a count, never
    individually -- BI-D4)."""
    in_scope: list[str] = []
    out_of_scope: list[str] = []
    dropped_unknown_asset_type = 0

    for entry in program.scopes:
        pattern = _translate_scope_entry(entry)
        if pattern is None:
            dropped_unknown_asset_type += 1
            continue
        (in_scope if entry.eligible_for_submission else out_of_scope).append(pattern)

    for entry in program.scope_exclusions:
        pattern = _translate_scope_entry(entry)
        if pattern is None:
            dropped_unknown_asset_type += 1
            continue
        out_of_scope.append(pattern)

    rules = ScopeRules(in_scope_regex=in_scope, out_of_scope_regex=out_of_scope)
    return rules, dropped_unknown_asset_type


def load_program_scope(
    program_handle: str, *, bucket: str, scope_uri: str | None = None
) -> ProgramScope:
    """The single entry point `scanner.main` calls: validate the handle,
    load (from `scope_uri` if given, else the derived per-engagement
    default), translate, and refuse to proceed if translation produced
    zero in-scope patterns.

    `ScopeRules` already denies everything on an empty `in_scope_regex` by
    construction (fail-closed belt), but this explicit check makes the
    failure diagnosable ("program X has zero in-scope assets after
    translation") instead of surfacing as an opaque scope-violation on the
    first candidate (the braces, not just the belt).
    """
    validate_program_handle(program_handle)
    uri = scope_uri or scope_uri_for_program(bucket, program_handle)
    program = load_roe(uri, program_handle)
    rules, dropped_unknown_asset_type = translate_program_scope(program)

    if not rules.in_scope_regex:
        raise RoEError(
            f"program {program_handle!r} translated to zero in-scope patterns "
            "-- refusing to scan"
        )

    return ProgramScope(
        rules=rules,
        program_handle=program_handle,
        platform=program.platform,
        synced_at=program.synced_at,
        identification=program.identification,
        dropped_unknown_asset_type=dropped_unknown_asset_type,
    )
