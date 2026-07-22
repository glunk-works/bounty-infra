"""RoE (rules-of-engagement) loading and scope translation (S1 Tasks 1/2).

Fail-closed throughout, deliberately NOT following scanner.py's
except-and-continue house style (BI-D8): every failure mode here --
object absent, access denied, undecryptable, malformed JSON, unknown
program handle, empty-after-translation -- raises `RoEError`. The caller
(`scanner.main`) must let that abort the process before any subprocess
runs.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

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
    model_config = ConfigDict(extra="forbid")

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


class RoEDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    programs: dict[str, Program]


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


def _parse_s3_uri(scope_uri: str) -> tuple[str, str]:
    parsed = urlparse(scope_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise RoEError(f"--scope-uri must be an s3://bucket/key URI, got {scope_uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def load_roe(scope_uri: str) -> RoEDocument:
    """Fetch and parse the RoE document from S3. S3 performs KMS decryption
    server-side (given `s3:GetObject` + `kms:Decrypt` on the caller's role
    -- IAM grant lives in glunk-works/global-bootstrap, not here); this
    function does no manual decrypt call.
    """
    bucket, key = _parse_s3_uri(scope_uri)
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
        return RoEDocument.model_validate(payload)
    except ValidationError as exc:
        raise RoEError(
            f"RoE object s3://{bucket}/{key} does not match the expected schema: {exc}"
        ) from exc


def select_program(doc: RoEDocument, program_handle: str) -> Program:
    program = doc.programs.get(program_handle)
    if program is None:
        raise RoEError(
            f"program {program_handle!r} is not present in the RoE document "
            f"(known handles: {sorted(doc.programs)})"
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


def load_program_scope(scope_uri: str, program_handle: str) -> ProgramScope:
    """The single entry point `scanner.main` calls: load, select, translate,
    and refuse to proceed if translation produced zero in-scope patterns.

    `ScopeRules` already denies everything on an empty `in_scope_regex` by
    construction (fail-closed belt), but this explicit check makes the
    failure diagnosable ("program X has zero in-scope assets after
    translation") instead of surfacing as an opaque scope-violation on the
    first candidate (the braces, not just the belt).
    """
    doc = load_roe(scope_uri)
    program = select_program(doc, program_handle)
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
