# Production Readiness Cleanup Report

**Date:** 2026-02-17
**Branch:** `chore/production-readiness-cleanup`

## Summary

| Metric | Value |
|--------|-------|
| Files changed | 12 |
| Source + docs lines | -8 net (65 added, 73 removed) |
| Tests passing | 466/466 (100%) |
| Coverage | 91% (exceeds 85% target) |
| New violations | 0 (mypy, flake8, bandit unchanged) |

## Changes by File

| File Path | Action | Justification |
|-----------|--------|---------------|
| `src/local.settings.json.template` | Added 5 missing env vars, removed 2 obsolete, added inline docs | `ALLOWED_AP_EMAILS`, `FUNCTION_APP_URL`, `VENDOR_FUZZY_THRESHOLD`, `RATE_LIMIT_DISABLED`, `MAIL_INGEST_ENABLED` referenced in code but missing from template. Removed `STORAGE_ACCOUNT_NAME`/`STORAGE_ACCOUNT_KEY` (unused - superseded by Managed Identity). |
| `src/shared/deduplication.py` | Removed unused imports (`os`, `TableServiceClient`); fixed docstring | `os` and `TableServiceClient` not referenced after previous refactors. Docstring said "MD5 hash" but code uses SHA-256. |
| `src/shared/rate_limiter.py` | Removed dead function `create_rate_limit_table()`, removed unused `TableServiceClient` import | Function defined but never called anywhere in codebase (zero callers, zero tests). |
| `src/SubscriptionManager/__init__.py` | Removed unused imports (`timedelta`, `TableServiceClient`, `generate_ulid`) | These symbols were imported but never used in the module. |
| `CLAUDE.md` | Fixed poison queue retry count: 5 -> 3 | `host.json` has `maxDequeueCount: 3`. Previously identified in Dec 2024 audit (REMEDIATION_PLAN_2024-12.md) but never fixed. |
| `docs/ARCHITECTURE.md` | Fixed poison queue retry count: 5 -> 3; fixed Health endpoint route `/api/Health` -> `/api/health` | `host.json` has `maxDequeueCount: 3`. Health `function.json` specifies `"route": "health"` (lowercase). |
| `docs/monitoring/MONITORING_GUIDE.md` | Fixed poison queue retry count: 5 -> 3 | Consistent with `host.json` `maxDequeueCount: 3`. |
| `docs/api/ADDVENDOR_API.md` | Fixed auth level, request schema, idempotency docs, rate limiting | `function.json` has `authLevel: function` (not open). Request schema referenced non-existent `vendor_domain`/`billing_party` fields. Code uses `create_entity` (not upsert). Rate limiting is 10/min (not unlimited). |
| `README.md` | Updated environment variables section | Added required/optional categorization, added 7 missing variables, added reference to template file. |
| `src/Health/__init__.py` | Black reformatted | No functional changes. |
| `tests/unit/test_email_processor.py` | Black reformatted | No functional changes. |
| `tests/unit/test_health.py` | Black reformatted | No functional changes. |

## Phase Details

### Phase 1: Environment Variable Audit

**Added to template:**
- `ALLOWED_AP_EMAILS` - Comma-separated AP email whitelist for loop prevention (referenced in `shared/config.py:215`)
- `FUNCTION_APP_URL` - Function App base URL for registration emails (referenced in `shared/config.py:241`)
- `VENDOR_FUZZY_THRESHOLD` - Fuzzy match confidence 0-100 (referenced in `shared/vendor_matcher.py:23`)
- `RATE_LIMIT_DISABLED` - Disable rate limiting for local dev (referenced in `shared/rate_limiter.py:132`)
- `MAIL_INGEST_ENABLED` - Disable hourly fallback polling (referenced in `MailIngest/__init__.py:26`)

**Removed from template:**
- `STORAGE_ACCOUNT_NAME` - Not referenced in any `.py` file in `src/` (superseded by Managed Identity)
- `STORAGE_ACCOUNT_KEY` - Not referenced in any `.py` file in `src/` (superseded by Managed Identity)

**Intentionally omitted:**
- `GIT_SHA`/`DEPLOYMENT_TIMESTAMP` - Set by CI/CD pipeline, not relevant for local dev

### Phase 2: Code Quality Improvements

**Unused imports removed (3 files, 5 imports):**
- `src/shared/deduplication.py`: `os`, `TableServiceClient`
- `src/SubscriptionManager/__init__.py`: `timedelta`, `TableServiceClient`, `generate_ulid`
- `src/shared/rate_limiter.py`: `TableServiceClient` (after dead code removal)

**Dead code removed:**
- `src/shared/rate_limiter.py`: `create_rate_limit_table()` function (12 lines) - zero callers, zero tests

**Docstring fix:**
- `src/shared/deduplication.py:120`: "MD5 hash" corrected to "SHA-256 hash"

**Dependency audit:**
- All packages in `requirements.txt` are actively used
- All packages have pinned versions (with appropriate ranges for security patches)

### Phase 3: Documentation Reconciliation

**Poison queue retry count (3 files):**
- `CLAUDE.md:337`: "5 retry attempts" -> "3 dequeue attempts (maxDequeueCount in host.json)"
- `docs/ARCHITECTURE.md:1267`: "After 5 failed attempts" -> "After 3 failed attempts"
- `docs/monitoring/MONITORING_GUIDE.md:101`: "5 retry attempts" -> "3 dequeue attempts"

**Health endpoint route:**
- `docs/ARCHITECTURE.md:136`: `GET /api/Health` -> `GET /api/health`

**AddVendor API doc (major corrections):**
- Authentication: "None (open)" -> "Function key required (authLevel: function)"
- Request schema: Removed non-existent `vendor_domain`/`billing_party` fields, added `product_category`/`venue_required`
- Idempotency: "upsert semantics" -> "create semantics (rejects duplicates)"
- Rate limiting: "No rate limiting" -> "10 requests/minute per IP"
- Storage key pattern: "vendor_domain normalized" -> "vendor_name normalized"

**README environment variables:**
- Reorganized into Required/Required for webhooks/Optional sections
- Added 7 previously undocumented variables

### Phase 4: Dead Code Removal

**Removed:**
- `create_rate_limit_table()` in `src/shared/rate_limiter.py` (12 lines + 1 import)

**Retained (test-only utilities):**
- `normalize_vendor_name()` in `src/shared/vendor_matcher.py` - has tests, useful public API
- `get_all_vendor_names()` in `src/shared/vendor_matcher.py` - has tests, useful public API

## Pre-existing Issues (Not Addressed)

These exist in the codebase before and after this cleanup:

| Issue | Location | Notes |
|-------|----------|-------|
| 16 mypy strict errors | Various (Optional narrowing) | Pre-existing; Config properties return Optional types |
| 8 flake8 warnings | Test files only (unused imports) | Pre-existing in tests |
| 1 bandit B110 | SubscriptionManager:117 | Pre-existing try/except/pass for table creation |
| 4 deprecation warnings | test_deduplication.py | Pre-existing; `datetime.utcnow()` usage in tests |
