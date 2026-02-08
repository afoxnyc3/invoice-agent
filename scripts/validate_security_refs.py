#!/usr/bin/env python3
"""Validate that symbols referenced in docs/SECURITY_CONTROLS.md still exist.

Run manually:
    python scripts/validate_security_refs.py

Also runs as part of CI (see .github/workflows/ci-cd.yml, validate-docs job).

Exit codes:
    0 — all references valid
    1 — one or more references missing
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Reference registry
#
# Each entry is (file_relative_to_repo, pattern_substring).
# The validator checks that *pattern* appears somewhere in *file*.
# Patterns are plain substrings (not regex) — keep them short and stable.
# ---------------------------------------------------------------------------

REFERENCES: list[tuple[str, str]] = [
    # ── 1. Identity & Access Control ──────────────────────────────────────
    # Managed Identity
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "type: 'SystemAssigned'",
    ),
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "AzureWebJobsStorage__credential",
    ),
    # RBAC roles
    (
        "infrastructure/bicep/modules/rbac.bicep",
        "storageBlobDataContributor",
    ),
    (
        "infrastructure/bicep/modules/rbac.bicep",
        "storageQueueDataContributor",
    ),
    (
        "infrastructure/bicep/modules/rbac.bicep",
        "storageTableDataContributor",
    ),
    (
        "infrastructure/bicep/modules/rbac.bicep",
        "keyVaultSecretsUser",
    ),
    # Python SDK identity usage
    ("src/shared/config.py", "DefaultAzureCredential"),
    # Graph API auth
    ("src/shared/graph_client.py", "ConfidentialClientApplication"),
    ("src/shared/graph_client.py", "_get_access_token"),
    ("src/shared/graph_client.py", "Bearer"),
    # ── 2. Secrets Management ─────────────────────────────────────────────
    # Key Vault configuration
    (
        "infrastructure/bicep/modules/keyvault.bicep",
        "enableSoftDelete: true",
    ),
    (
        "infrastructure/bicep/modules/keyvault.bicep",
        "enablePurgeProtection: true",
    ),
    (
        "infrastructure/bicep/modules/keyvault.bicep",
        "secrets: [",
    ),
    # Key Vault audit logging
    (
        "infrastructure/bicep/modules/keyvault.bicep",
        "category: 'AuditEvent'",
    ),
    # Key Vault references in function app
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "@Microsoft.KeyVault(",
    ),
    # Secret consumption in Python
    ("src/shared/config.py", "os.environ"),
    # Gitleaks in CI
    (".github/workflows/ci-cd.yml", "gitleaks"),
    # ── 3. Transport Security ─────────────────────────────────────────────
    # Function App TLS / HTTPS
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "httpsOnly: true",
    ),
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "minTlsVersion: '1.2'",
    ),
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "scmMinTlsVersion: '1.2'",
    ),
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "http20Enabled: true",
    ),
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "ftpsState: 'Disabled'",
    ),
    # Storage TLS / HTTPS
    (
        "infrastructure/bicep/modules/storage.bicep",
        "supportsHttpsTrafficOnly: true",
    ),
    (
        "infrastructure/bicep/modules/storage.bicep",
        "minimumTlsVersion: 'TLS1_2'",
    ),
    (
        "infrastructure/bicep/modules/storage.bicep",
        "allowBlobPublicAccess: false",
    ),
    # CORS locked down
    (
        "infrastructure/bicep/modules/functionapp.bicep",
        "allowedOrigins: []",
    ),
    (
        "infrastructure/bicep/modules/storage.bicep",
        "corsRules: []",
    ),
    # External API URLs
    ("src/shared/graph_client.py", "graph.microsoft.com"),
    # ── 4. Data Protection ────────────────────────────────────────────────
    (
        "infrastructure/bicep/modules/storage.bicep",
        "deleteRetentionPolicy",
    ),
    (
        "infrastructure/bicep/modules/storage.bicep",
        "containerDeleteRetentionPolicy",
    ),
    (
        "infrastructure/bicep/modules/storage.bicep",
        "publicAccess: 'None'",
    ),
    # Pydantic models
    ("src/shared/models.py", "class RawMail"),
    ("src/shared/models.py", "class EnrichedInvoice"),
    ("src/shared/models.py", "class VendorMaster"),
    ("src/shared/models.py", "class InvoiceTransaction"),
    ("src/shared/models.py", "class NotificationMessage"),
    # OData injection prevention
    ("src/shared/deduplication.py", "_sanitize_odata_string"),
    # ── 5. Application-Level Controls ─────────────────────────────────────
    # Webhook security
    ("src/MailWebhook/__init__.py", "validationToken"),
    ("src/MailWebhook/__init__.py", "clientState"),
    ("src/MailWebhook/__init__.py", "RATE_LIMIT_MAX_REQUESTS"),
    # Rate limiting
    ("src/shared/rate_limiter.py", "check_rate_limit"),
    ("src/shared/rate_limiter.py", "get_client_ip"),
    # Circuit breakers
    ("src/shared/circuit_breaker.py", "graph_breaker"),
    ("src/shared/circuit_breaker.py", "openai_breaker"),
    ("src/shared/circuit_breaker.py", "storage_breaker"),
    # Deduplication
    ("src/shared/deduplication.py", "is_message_already_processed"),
    ("src/shared/deduplication.py", "check_duplicate_invoice"),
    # ── 6. CI/CD Security ─────────────────────────────────────────────────
    (".github/workflows/ci-cd.yml", "flake8"),
    (".github/workflows/ci-cd.yml", "black"),
    (".github/workflows/ci-cd.yml", "add-mask"),
    (".github/workflows/ci-cd.yml", "AZURE_CREDENTIALS"),
]


def validate() -> list[str]:
    """Return list of error messages for missing references."""
    errors: list[str] = []
    # Cache file contents to avoid re-reading
    cache: dict[str, str | None] = {}

    for rel_path, pattern in REFERENCES:
        if rel_path not in cache:
            full = REPO_ROOT / rel_path
            if full.is_file():
                cache[rel_path] = full.read_text(encoding="utf-8")
            else:
                cache[rel_path] = None

        content = cache[rel_path]
        if content is None:
            errors.append(f"MISSING FILE: {rel_path}")
        elif pattern not in content:
            errors.append(
                f"MISSING SYMBOL: '{pattern}' not found in {rel_path}"
            )

    return errors


def main() -> None:
    errors = validate()
    total = len(REFERENCES)

    if errors:
        print(f"FAIL — {len(errors)}/{total} reference(s) broken:\n")
        for err in errors:
            print(f"  {err}")
        print(
            "\nUpdate docs/SECURITY_CONTROLS.md and "
            "scripts/validate_security_refs.py together."
        )
        sys.exit(1)
    else:
        print(f"OK — all {total} security doc references valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
