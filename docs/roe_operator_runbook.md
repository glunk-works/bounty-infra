# RoE operator runbook

**Audience: the human operator, not CI.** S1 (`src/bounty_scanner/roe.py`) ships the
*mechanism* — a fail-closed loader that refuses to scan without a valid, matching RoE
object. It does not and cannot ship the RoE *content*: that is real per-engagement
authorization data, and per `CLAUDE.md` § *what must not be committed* it never belongs in
this repo. This doc is the missing piece — how an operator actually gets a real RoE object
in place so a dispatched scan can run.

## Layout (BI-D9)

One object **per engagement**, no wrapping map:

```
s3://<findings-bucket>/roe/<program-handle>/scope.json
```

`<program-handle>` must match `^[A-Za-z0-9][A-Za-z0-9_-]*$` (`roe.py`'s
`_PROGRAM_HANDLE_RE`) — it participates directly in the S3 key. `<findings-bucket>` is
account-specific and resolves at runtime via Infisical / the `S3_BUCKET_NAME` env var the
task definition already carries; it is deliberately not written down here (BI-D4).

## Document shape

The file *is* the program document — every field below is required unless marked
optional. `handle` **must** equal `<program-handle>` in the S3 key; `roe.py` hard-fails on
a mismatch rather than silently trusting the key.

```jsonc
// TEMPLATE — placeholder data only. Replace every value with the real engagement's
// scope before uploading. example.com is not a real target.
{
  "version": 1,
  "platform": "hackerone",
  "handle": "example-program",
  "synced_at": "2026-07-22T00:00:00Z",
  "scopes": [
    { "asset_type": "URL", "asset_identifier": "https://app.example.com", "eligible_for_submission": true },
    { "asset_type": "WILDCARD", "asset_identifier": "*.example.com", "eligible_for_submission": true },
    { "asset_type": "URL", "asset_identifier": "https://staging.example.com", "eligible_for_submission": false }
  ],
  "scope_exclusions": [
    { "asset_type": "WILDCARD", "asset_identifier": "*.internal.example.com" }
  ],
  "identification": {
    "ua_suffix": null,
    "headers": {}
  }
}
```

Notes on the fields, from `roe.py`:

- `platform`: free text today (`"hackerone"` / `"bugcrowd"`), used for logging only.
- `scopes[].asset_type`: only `URL` and `WILDCARD` translate to a scan pattern
  (`_ALLOWED_ASSET_TYPES`) — every other HackerOne asset type (`SOURCE_CODE`, `HARDWARE`,
  app-store IDs, CIDR, `IP_ADDRESS`, anything added later) is dropped and counted, never
  fed to `subfinder` as a hostname.
- `scopes[].eligible_for_submission: false` and `scope_exclusions[]` are **two separate**
  out-of-scope sources (BI-D9) — HackerOne exposes explicit exclusions via its own API
  endpoint, distinct from the per-asset flag. Both must be populated for a Bugcrowd program
  too, since Bugcrowd has no equivalent API to source them from automatically; a human
  transcribes them into this same shape.
- `identification`: optional. Omit entirely (or leave both sub-fields empty/null) to fall
  back to the global default User-Agent (S1 Task 4). Only set `ua_suffix`/`headers` if this
  specific program requires an identification override.

## Uploading

From a machine with the operator's own AWS session (this write path does not go through
CI — the same "no laptop by design" boundary as a real `tofu apply`):

```bash
aws s3 cp scope.json "s3://<findings-bucket>/roe/<program-handle>/scope.json" \
  --sse aws:kms --sse-kms-key-id "<kms-key-arn>"
```

Resolve `<findings-bucket>` and `<kms-key-arn>` the same way any other account-specific
value in this system resolves — Infisical, or a `tofu output` in `global-bootstrap` (which
owns both). The task role already holds `s3:PutObject`/`s3:GetObject`/`s3:ListBucket` on
the findings bucket and `kms:Encrypt`/`kms:Decrypt`/`kms:GenerateDataKey*` on that key
(`infra/main.tf`) — nothing here changes IAM.

## Verifying before a real dispatch

`load_program_scope` is fail-closed on every failure mode (object absent, access denied,
undecryptable, malformed JSON, handle mismatch, empty-after-translation) — a scan simply
refuses to run rather than running under-scoped or unscoped. There is currently no
operator-facing dry-run command that exercises this without a real `workflow_dispatch`;
the closest verification today is `hatch run test:run -- test_roe.py`, which covers the
loader's behavior against synthetic fixtures, not the real uploaded object. Treat the first
real dispatch against a newly-uploaded RoE as the actual verification.

## Status

As of 2026-07-22, this is the one remaining gate on S1 working end-to-end: the mechanism
is merged, but no real RoE object exists yet for either engagement (HackerOne, Bugcrowd).
See `.ai/next-steps.md` for the live cursor.
