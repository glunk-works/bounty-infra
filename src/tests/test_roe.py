import json

import pytest
from botocore.exceptions import ClientError

from bounty_scanner.roe import (
    Program,
    RoEError,
    ScopeEntry,
    load_program_scope,
    load_roe,
    scope_uri_for_program,
    translate_program_scope,
    validate_program_handle,
)

VALID_PROGRAM = {
    "version": 1,
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
# TESTS FOR: validate_program_handle -- now guards an S3 key, not just a
# dict lookup (BI-D9 revision, S1).
# ==========================================


@pytest.mark.parametrize("handle", ["acme", "acme-vdp", "acme_2", "A1"])
def test_validate_program_handle_accepts_reasonable_shapes(handle):
    validate_program_handle(handle)  # must not raise


@pytest.mark.parametrize(
    "handle",
    ["", "../etc", "acme/other", "acme.com", "acme scope", "-acme", "acme;rm -rf"],
)
def test_validate_program_handle_rejects_unreasonable_shapes(handle):
    with pytest.raises(RoEError):
        validate_program_handle(handle)


# ==========================================
# TESTS FOR: scope_uri_for_program
# ==========================================


def test_scope_uri_for_program_shape():
    assert scope_uri_for_program("findings-bucket", "acme") == "s3://findings-bucket/roe/acme/scope.json"


# ==========================================
# TESTS FOR: load_roe -- every failure mode aborts, none call a subprocess
# (roe.py itself never touches subprocess; the acceptance criterion this
# pins is "raises RoEError", which scanner.main() turns into sys.exit(1)
# before run_recon_pipeline is ever entered).
# ==========================================


def test_load_roe_success(mocker):
    _mock_s3_get_object(mocker, body=json.dumps(VALID_PROGRAM).encode())
    program = load_roe("s3://test-bucket/roe/acme/scope.json", "acme")
    assert isinstance(program, Program)
    assert program.handle == "acme"


def test_load_roe_rejects_non_s3_uri():
    with pytest.raises(RoEError):
        load_roe("https://example.com/scope.json", "acme")


def test_load_roe_rejects_missing_key():
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket", "acme")


def test_load_roe_object_absent(mocker):
    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject")
    _mock_s3_get_object(mocker, error=error)
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/acme/scope.json", "acme")


def test_load_roe_access_denied(mocker):
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetObject")
    _mock_s3_get_object(mocker, error=error)
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/acme/scope.json", "acme")


def test_load_roe_malformed_json(mocker):
    _mock_s3_get_object(mocker, body=b"{not valid json")
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/acme/scope.json", "acme")


def test_load_roe_malformed_schema(mocker):
    _mock_s3_get_object(mocker, body=json.dumps({"version": 1}).encode())
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/acme/scope.json", "acme")


def test_load_roe_unknown_extra_field_rejected(mocker):
    bad = dict(VALID_PROGRAM, unexpected_top_level_field=True)
    _mock_s3_get_object(mocker, body=json.dumps(bad).encode())
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/acme/scope.json", "acme")


def test_load_roe_handle_mismatch_rejected(mocker):
    """Self-consistency check that only matters now that the S3 key IS the
    selector: a misnamed prefix or copy-pasted file must not silently apply
    the wrong engagement's rules under the right-looking key."""
    _mock_s3_get_object(mocker, body=json.dumps(VALID_PROGRAM).encode())
    with pytest.raises(RoEError):
        load_roe("s3://test-bucket/roe/othercorp/scope.json", "othercorp")


# ==========================================
# TESTS FOR: translate_program_scope -- the sharpest risk in S1 (Task 2)
# ==========================================


def test_translate_eligible_true_becomes_in_scope():
    program = Program.model_validate(VALID_PROGRAM)
    rules, _ = translate_program_scope(program)
    assert any("shop\\.acme\\.com" in p for p in rules.in_scope_regex)


def test_translate_eligible_false_becomes_out_of_scope():
    program = Program.model_validate(VALID_PROGRAM)
    rules, _ = translate_program_scope(program)
    assert any("internal\\.acme\\.com" in p for p in rules.out_of_scope_regex)


def test_translate_scope_exclusions_become_out_of_scope_unconditionally():
    program = Program.model_validate(VALID_PROGRAM)
    rules, _ = translate_program_scope(program)
    assert any("legacy\\.acme\\.com" in p for p in rules.out_of_scope_regex)


def test_translate_unknown_asset_type_dropped_and_counted():
    program = Program.model_validate(VALID_PROGRAM)
    rules, dropped = translate_program_scope(program)
    assert dropped == 1  # the SOURCE_CODE entry
    joined = " ".join(rules.in_scope_regex + rules.out_of_scope_regex)
    assert "github.com/acme/repo" not in joined


def test_translate_url_pattern_escapes_and_anchors():
    program = Program(
        version=1,
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
        version=1,
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
        version=1,
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


def test_load_program_scope_success_via_derived_uri(mocker):
    mock_s3 = _mock_s3_get_object(mocker, body=json.dumps(VALID_PROGRAM).encode())
    scope = load_program_scope("acme", bucket="findings-bucket")
    assert scope.program_handle == "acme"
    assert scope.platform == "hackerone"
    assert scope.dropped_unknown_asset_type == 1
    assert scope.identification.ua_suffix == "acme-vdp"
    mock_s3.get_object.assert_called_once_with(Bucket="findings-bucket", Key="roe/acme/scope.json")


def test_load_program_scope_success_via_explicit_override(mocker):
    mock_s3 = _mock_s3_get_object(mocker, body=json.dumps(VALID_PROGRAM).encode())
    load_program_scope("acme", bucket="findings-bucket", scope_uri="s3://other-bucket/custom/path.json")
    mock_s3.get_object.assert_called_once_with(Bucket="other-bucket", Key="custom/path.json")


def test_load_program_scope_invalid_handle_rejected_before_any_s3_call(mocker):
    mock_s3 = _mock_s3_get_object(mocker, body=json.dumps(VALID_PROGRAM).encode())
    with pytest.raises(RoEError):
        load_program_scope("../etc", bucket="findings-bucket")
    mock_s3.get_object.assert_not_called()


def test_load_program_scope_empty_after_translation_raises(mocker):
    doc = {
        "version": 1,
        "platform": "hackerone",
        "handle": "empty",
        "synced_at": "2026-01-01T00:00:00Z",
        "scopes": [
            {"asset_type": "SOURCE_CODE", "asset_identifier": "github.com/x/y", "eligible_for_submission": True}
        ],
    }
    _mock_s3_get_object(mocker, body=json.dumps(doc).encode())
    with pytest.raises(RoEError):
        load_program_scope("empty", bucket="findings-bucket")


def test_load_program_scope_no_identification_falls_back_to_none(mocker):
    doc = {
        "version": 1,
        "platform": "hackerone",
        "handle": "bare",
        "synced_at": "2026-01-01T00:00:00Z",
        "scopes": [{"asset_type": "URL", "asset_identifier": "bare.com", "eligible_for_submission": True}],
    }
    _mock_s3_get_object(mocker, body=json.dumps(doc).encode())
    scope = load_program_scope("bare", bucket="findings-bucket")
    assert scope.identification is None
