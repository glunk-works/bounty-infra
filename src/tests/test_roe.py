import json

import pytest
from botocore.exceptions import ClientError

from bounty_scanner.roe import (
    Program,
    RoEDocument,
    RoEError,
    ScopeEntry,
    load_program_scope,
    load_roe,
    select_program,
    translate_program_scope,
)

VALID_DOC = {
    "version": 1,
    "programs": {
        "acme": {
            "platform": "hackerone",
            "handle": "acme",
            "synced_at": "2026-07-22T00:00:00Z",
            "scopes": [
                {"asset_type": "WILDCARD", "asset_identifier": "*.acme.com", "eligible_for_submission": True},
                {"asset_type": "URL", "asset_identifier": "shop.acme.com", "eligible_for_submission": True},
                {"asset_type": "URL", "asset_identifier": "internal.acme.com", "eligible_for_submission": False},
                {"asset_type": "SOURCE_CODE", "asset_identifier": "github.com/acme/repo", "eligible_for_submission": True},
            ],
            "scope_exclusions": [
                {"asset_type": "URL", "asset_identifier": "legacy.acme.com"},
            ],
            "identification": {"ua_suffix": "acme-vdp", "headers": {"X-Bug-Bounty": "acme"}},
        }
    },
}


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


def _mock_s3_get_object(mocker, body: bytes = None, error: Exception = None):
    mock_s3 = mocker.MagicMock()
    if error is not None:
        mock_s3.get_object.side_effect = error
    else:
        mock_s3.get_object.return_value = {"Body": _FakeBody(body)}
    mocker.patch("bounty_scanner.roe.boto3.client", return_value=mock_s3)
    return mock_s3


# ==========================================
# TESTS FOR: load_roe -- every failure mode aborts, none call a subprocess
# (roe.py itself never touches subprocess; the acceptance criterion this
# pins is "raises RoEError", which scanner.main() turns into sys.exit(1)
# before run_recon_pipeline is ever entered).
# ==========================================


def test_load_roe_success(mocker):
    _mock_s3_get_object(mocker, body=json.dumps(VALID_DOC).encode())
    doc = load_roe("s3://test-bucket/roe/scope.json")
    assert isinstance(doc, RoEDocument)
    assert doc.version == 1
    assert "acme" in doc.programs


def test_load_roe_rejects_non_s3_uri():
    with pytest.raises(RoEError):
        load_roe("https://example.com/scope.json")


def test_load_roe_object_absent(mocker):
    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject")
    _mock_s3_get_object(mocker, error=error)
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/scope.json")


def test_load_roe_access_denied(mocker):
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetObject")
    _mock_s3_get_object(mocker, error=error)
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/scope.json")


def test_load_roe_malformed_json(mocker):
    _mock_s3_get_object(mocker, body=b"{not valid json")
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/scope.json")


def test_load_roe_malformed_schema(mocker):
    _mock_s3_get_object(mocker, body=json.dumps({"version": 1, "programs": "not-a-dict"}).encode())
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/scope.json")


def test_load_roe_unknown_extra_field_rejected(mocker):
    bad = {"version": 1, "programs": {}, "unexpected_top_level_field": True}
    _mock_s3_get_object(mocker, body=json.dumps(bad).encode())
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/scope.json")


# ==========================================
# TESTS FOR: select_program
# ==========================================


def test_select_program_known_handle():
    doc = RoEDocument.model_validate(VALID_DOC)
    program = select_program(doc, "acme")
    assert program.handle == "acme"


def test_select_program_unknown_handle_raises():
    doc = RoEDocument.model_validate(VALID_DOC)
    with pytest.raises(RoEError):
        select_program(doc, "not-a-real-program")


# ==========================================
# TESTS FOR: translate_program_scope -- the sharpest risk in S1 (Task 2)
# ==========================================


def test_translate_eligible_true_becomes_in_scope():
    program = Program.model_validate(VALID_DOC["programs"]["acme"])
    rules, _ = translate_program_scope(program)
    assert any("shop\\.acme\\.com" in p for p in rules.in_scope_regex)


def test_translate_eligible_false_becomes_out_of_scope():
    program = Program.model_validate(VALID_DOC["programs"]["acme"])
    rules, _ = translate_program_scope(program)
    assert any("internal\\.acme\\.com" in p for p in rules.out_of_scope_regex)


def test_translate_scope_exclusions_become_out_of_scope_unconditionally():
    program = Program.model_validate(VALID_DOC["programs"]["acme"])
    rules, _ = translate_program_scope(program)
    assert any("legacy\\.acme\\.com" in p for p in rules.out_of_scope_regex)


def test_translate_unknown_asset_type_dropped_and_counted():
    program = Program.model_validate(VALID_DOC["programs"]["acme"])
    rules, dropped = translate_program_scope(program)
    assert dropped == 1  # the SOURCE_CODE entry
    joined = " ".join(rules.in_scope_regex + rules.out_of_scope_regex)
    assert "github.com/acme/repo" not in joined


def test_translate_url_pattern_escapes_and_anchors():
    program = Program(
        platform="hackerone",
        handle="p",
        synced_at="2026-01-01T00:00:00Z",
        scopes=[
            ScopeEntry(asset_type="URL", asset_identifier="example.com", eligible_for_submission=True)
        ],
    )
    rules, _ = translate_program_scope(program)
    import re

    pattern = rules.in_scope_regex[0]
    assert re.search(pattern, "example.com")
    # rule 1: escaped -- an unescaped '.' would match 'exampleXcom'
    assert not re.search(pattern, "exampleXcom")
    # rule 2: anchored -- unanchored, this would match a substring
    assert not re.search(pattern, "example.com.attacker.net")
    assert not re.search(pattern, "evil-example.com")


def test_translate_wildcard_pattern_adversarial():
    program = Program(
        platform="hackerone",
        handle="p",
        synced_at="2026-01-01T00:00:00Z",
        scopes=[
            ScopeEntry(asset_type="WILDCARD", asset_identifier="*.example.com", eligible_for_submission=True)
        ],
    )
    rules, _ = translate_program_scope(program)
    import re

    pattern = rules.in_scope_regex[0]
    # A real subdomain must match.
    assert re.search(pattern, "foo.example.com")
    assert re.search(pattern, "foo.bar.example.com")
    # rule 3: apex excluded by default.
    assert not re.search(pattern, "example.com")
    # Must NOT match a superstring host (unanchored-suffix attack).
    assert not re.search(pattern, "evil.example.com.attacker.net")
    # Must NOT match a lookalike domain with no literal dot before the label.
    assert not re.search(pattern, "evil-example.com")
    assert not re.search(pattern, "fooexample.com")


def test_translate_wildcard_malformed_identifier_falls_back_to_literal():
    # An asset_identifier claiming WILDCARD but not shaped like one --
    # treat as a literal host, never widen to "match anything".
    program = Program(
        platform="hackerone",
        handle="p",
        synced_at="2026-01-01T00:00:00Z",
        scopes=[
            ScopeEntry(asset_type="WILDCARD", asset_identifier="example.com", eligible_for_submission=True)
        ],
    )
    rules, _ = translate_program_scope(program)
    import re

    pattern = rules.in_scope_regex[0]
    assert re.search(pattern, "example.com")
    assert not re.search(pattern, "foo.example.com")


# ==========================================
# TESTS FOR: load_program_scope -- the single fail-closed entry point
# ==========================================


def test_load_program_scope_success(mocker):
    _mock_s3_get_object(mocker, body=json.dumps(VALID_DOC).encode())
    scope = load_program_scope("s3://test-bucket/roe/scope.json", "acme")
    assert scope.program_handle == "acme"
    assert scope.platform == "hackerone"
    assert scope.dropped_unknown_asset_type == 1
    assert scope.identification.ua_suffix == "acme-vdp"


def test_load_program_scope_unknown_handle_raises_before_translation(mocker):
    _mock_s3_get_object(mocker, body=json.dumps(VALID_DOC).encode())
    with pytest.raises(RoEError):
        load_program_scope("s3://test-bucket/roe/scope.json", "nope")


def test_load_program_scope_empty_after_translation_raises(mocker):
    doc = {
        "version": 1,
        "programs": {
            "empty": {
                "platform": "hackerone",
                "handle": "empty",
                "synced_at": "2026-01-01T00:00:00Z",
                "scopes": [
                    {"asset_type": "SOURCE_CODE", "asset_identifier": "github.com/x/y", "eligible_for_submission": True}
                ],
            }
        },
    }
    _mock_s3_get_object(mocker, body=json.dumps(doc).encode())
    with pytest.raises(RoEError):
        load_program_scope("s3://test-bucket/roe/scope.json", "empty")


def test_load_program_scope_no_identification_falls_back_to_none(mocker):
    doc = {
        "version": 1,
        "programs": {
            "bare": {
                "platform": "hackerone",
                "handle": "bare",
                "synced_at": "2026-01-01T00:00:00Z",
                "scopes": [
                    {"asset_type": "URL", "asset_identifier": "bare.com", "eligible_for_submission": True}
                ],
            }
        },
    }
    _mock_s3_get_object(mocker, body=json.dumps(doc).encode())
    scope = load_program_scope("s3://test-bucket/roe/scope.json", "bare")
    assert scope.identification is None
