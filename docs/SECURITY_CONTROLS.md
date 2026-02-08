# Invoice Agent — Security Controls Assessment

> **Maintenance:** This document references source code by symbol, property name, and
> section identifier rather than line numbers. References should be verified quarterly
> or after major refactors. Run `python scripts/validate_security_refs.py` (also
> executed in CI) to check that all referenced symbols still exist. Update this
> document and the validation script together when controls change.

**Version:** 2.0
**Last Updated:** 2026-02-08
**Maintained By:** Engineering Team

---

## Executive Summary

The Invoice Agent implements **defense-in-depth** across 7 security layers: identity, secrets management, transport security, data protection, application-level controls, CI/CD security, and operational procedures. All Azure resource access uses **Managed Identity with RBAC** — no shared keys or connection strings in production. Secrets are centralized in **Key Vault** with audit logging, and all endpoints enforce **HTTPS with TLS 1.2 minimum**.

---

## 1. Identity & Access Control (RBAC + Managed Identity)

### System-Assigned Managed Identity

Both the production Function App and staging slot use **system-assigned Managed Identity**, meaning Azure automatically provisions and rotates credentials with zero operator involvement.

| Resource | File | Section |
|---|---|---|
| Production slot identity | `infrastructure/bicep/modules/functionapp.bicep` | `functionApp` resource: `identity { type: 'SystemAssigned' }` block |
| Staging slot identity | `infrastructure/bicep/modules/functionapp.bicep` | `stagingSlot` resource: `identity { type: 'SystemAssigned' }` block |

The Function App authenticates to Storage via identity-based connection settings — no connection string needed:

```bicep
AzureWebJobsStorage__credential = 'managedidentity'
AzureWebJobsStorage__accountName = storageAccountName
AzureWebJobsStorage__blobServiceUri = 'https://...'
AzureWebJobsStorage__queueServiceUri = 'https://...'
AzureWebJobsStorage__tableServiceUri = 'https://...'
```

*(functionapp.bicep: `AzureWebJobsStorage__credential` app settings block)*

### RBAC Role Assignments (8 total)

All defined in `infrastructure/bicep/modules/rbac.bicep`, `roles` variable block:

| Role | GUID | Scope | Slots |
|---|---|---|---|
| Storage Blob Data Contributor | `ba92f5b4-2d11-...` | Storage Account | Prod + Staging |
| Storage Queue Data Contributor | `974c5e8b-45b9-...` | Storage Account | Prod + Staging |
| Storage Table Data Contributor | `0a9a7e1f-b9d0-...` | Storage Account | Prod + Staging |
| Key Vault Secrets User | `4633458b-17de-...` | Key Vault | Prod + Staging |

Each slot gets its own identity and its own 4 role assignments = **8 RBAC assignments total**. The Key Vault Secrets User role grants only `get` and `list` — no create, delete, or purge.

### Python SDK Usage

In `src/shared/config.py`, all Azure SDK clients use `DefaultAzureCredential()` which automatically resolves to the Managed Identity in production:

```python
credential = DefaultAzureCredential()
self._table_service = TableServiceClient(table_uri, credential=credential)
self._blob_service = BlobServiceClient(blob_uri, credential=credential)
self._queue_service = QueueServiceClient(queue_uri, credential=credential)
```

*(config.py: `DefaultAzureCredential()` client initializations in `table_service`, `blob_service`, `queue_service` properties)*

Falls back to connection string only for local development with Azurite.

### Graph API Authentication (Exception to MI)

Microsoft Graph API requires OAuth 2.0 client credentials — Managed Identity is not supported. Handled via MSAL:

```python
self.app = ConfidentialClientApplication(
    client_id=self.client_id,
    client_credential=self.client_secret,
    authority=f"https://login.microsoftonline.com/{self.tenant_id}",
)
```

*(graph_client.py: `ConfidentialClientApplication` initialization in `__init__`)*

Token management includes caching with a **5-minute refresh buffer** before expiry (`_get_access_token` method) and Bearer token injection on all requests (`_make_request_internal` method). Documented in **ADR-0010**.

---

## 2. Secrets Management (Key Vault)

### Key Vault Configuration

Defined in `infrastructure/bicep/modules/keyvault.bicep`, `keyVault` resource `properties` block:

| Setting | Value | Section |
|---|---|---|
| SKU | Standard | `sku { name: 'standard' }` |
| Soft Delete | Enabled, 90-day retention | `enableSoftDelete: true` / `softDeleteRetentionInDays: 90` |
| Purge Protection | Enabled | `enablePurgeProtection: true` |
| RBAC Authorization | false (uses access policies) | `enableRbacAuthorization: false` |
| Template Deployment | Enabled | `enabledForTemplateDeployment: true` |
| VM Deployment | Disabled | `enabledForDeployment: false` |
| Disk Encryption | Disabled | `enabledForDiskEncryption: false` |

### Access Policies (Least Privilege)

Both production and staging Managed Identities have **read-only secret access**:

```bicep
permissions: {
  secrets: ['get', 'list']
}
```

*(keyvault.bicep: `accessPolicies` array — `permissions { secrets: ['get', 'list'] }` blocks)*

No set, delete, backup, restore, or purge permissions granted.

### Secrets Inventory (9 secrets)

All Function App settings reference Key Vault via `@Microsoft.KeyVault()` syntax (functionapp.bicep: Key Vault reference app settings block):

| Secret | App Setting | Purpose |
|---|---|---|
| `graph-tenant-id` | GRAPH_TENANT_ID | Azure AD tenant |
| `graph-client-id` | GRAPH_CLIENT_ID | App registration |
| `graph-client-secret` | GRAPH_CLIENT_SECRET | OAuth credential |
| `graph-client-state` | GRAPH_CLIENT_STATE | Webhook validation token |
| `invoice-mailbox` | INVOICE_MAILBOX | Monitored mailbox address |
| `ap-email-address` | AP_EMAIL_ADDRESS | Destination AP inbox |
| `teams-webhook-url` | TEAMS_WEBHOOK_URL | Teams notifications |
| `azure-openai-endpoint` | AZURE_OPENAI_ENDPOINT | PDF extraction API |
| `azure-openai-api-key` | AZURE_OPENAI_API_KEY | OpenAI auth |

### Key Vault Audit Logging

Diagnostic settings send all access events to Log Analytics (keyvault.bicep: `keyVaultDiagnostics` resource):

- **AuditEvent** category: All data plane operations logged
- **AllMetrics**: Performance monitoring
- **Retention**: 90 days (via Log Analytics workspace, per ADR-0031)

### No Hardcoded Secrets

Verified across entire codebase:

- All Python code reads secrets from `os.environ` only (config.py: property accessors such as `graph_tenant_id`, `graph_client_id`, etc.)
- Test fixtures use clearly-marked `"test-"` prefixed values (tests/conftest.py: `mock_environment` fixture)
- `local.settings.json.template` uses `"your-*"` placeholders
- Gitleaks runs on every commit in CI/CD (ci-cd.yml: `Scan for secrets with Gitleaks` step)

### Rotation Procedures

Documented in `docs/operations/KEY_ROTATION.md` and `docs/operations/SECURITY_PROCEDURES.md`:

| Secret | Rotation Frequency | Procedure |
|---|---|---|
| Graph API Client Secret | 90 days | Regenerate in Azure AD, update KV, restart |
| Azure OpenAI API Key | 90 days | Regenerate in portal, update KV, restart |
| Teams Webhook URL | 180 days | Create new webhook in Teams, update KV |
| Storage Account Key | 90 days | Regenerate via CLI, update dependent SAS |

Each procedure includes rollback steps and 24-48 hour grace periods before old secret deletion.

---

## 3. Transport Security (HTTPS, TLS, FTPS)

### Function App

Defined in `infrastructure/bicep/modules/functionapp.bicep`, `functionApp` resource `siteConfig` block:

| Setting | Value | Section |
|---|---|---|
| `httpsOnly` | `true` | `functionApp` resource: `properties { httpsOnly: true }` |
| `minTlsVersion` | `'1.2'` | `siteConfig { minTlsVersion: '1.2' }` |
| `scmMinTlsVersion` | `'1.2'` | `siteConfig { scmMinTlsVersion: '1.2' }` |
| `http20Enabled` | `true` | `siteConfig { http20Enabled: true }` |
| `ftpsState` | `'Disabled'` | `siteConfig { ftpsState: 'Disabled' }` |

All HTTP requests are **redirected to HTTPS**. FTP/FTPS deployment is completely disabled — deployments use blob URL only (ADR-0034).

### Storage Account

Defined in `infrastructure/bicep/modules/storage.bicep`, `storageAccount` resource `properties` block:

| Setting | Value | Section |
|---|---|---|
| `supportsHttpsTrafficOnly` | `true` | `properties { supportsHttpsTrafficOnly: true }` |
| `minimumTlsVersion` | `'TLS1_2'` | `properties { minimumTlsVersion: 'TLS1_2' }` |
| `allowBlobPublicAccess` | `false` | `properties { allowBlobPublicAccess: false }` |

All storage service URIs in function app settings use `https://` explicitly (functionapp.bicep: `AzureWebJobsStorage__*ServiceUri` app settings).

### All External API Calls

- Graph API: `https://graph.microsoft.com/v1.0` (graph_client.py: `self.graph_url` assignment)
- MSAL Authority: `https://login.microsoftonline.com/{tenant}` (graph_client.py: `self.authority` assignment)
- Key Vault: `https://{name}.vault.azure.net/` (functionapp.bicep: `KEY_VAULT_URI` app setting)
- Azure OpenAI: HTTPS endpoint from Key Vault
- Teams Webhook: HTTPS URL from Key Vault

### CORS

Locked down to empty origins on all services:

| Service | Config | Section |
|---|---|---|
| Function App | `allowedOrigins: []` | functionapp.bicep: `siteConfig { cors { allowedOrigins: [] } }` |
| Blob Service | `corsRules: []` | storage.bicep: `blobServices` resource `cors { corsRules: [] }` |
| Queue Service | `corsRules: []` | storage.bicep: `queueServices` resource `cors { corsRules: [] }` |
| Table Service | `corsRules: []` | storage.bicep: `tableServices` resource `cors { corsRules: [] }` |

---

## 4. Data Protection

### Storage Data Protection

| Control | Prod | Dev | Section |
|---|---|---|---|
| Blob soft delete | 30 days | 7 days | storage.bicep: `blobServices` resource `deleteRetentionPolicy` |
| Container soft delete | 30 days | 7 days | storage.bicep: `blobServices` resource `containerDeleteRetentionPolicy` |
| Public blob access | Disabled | Disabled | storage.bicep: `allowBlobPublicAccess: false` property |
| Container public access | `'None'` | `'None'` | storage.bicep: `invoicesContainer` resource `publicAccess: 'None'` |

Container soft delete was added per AZQR Phase 1 recommendations (ADR-0031).

### Key Vault Data Protection

- **Soft delete**: 90-day retention (keyvault.bicep: `enableSoftDelete` / `softDeleteRetentionInDays` properties)
- **Purge protection**: Enabled — secrets cannot be permanently deleted during retention (keyvault.bicep: `enablePurgeProtection: true`)

### Pydantic Model Validation

All queue messages and table entities are validated through strict Pydantic models (`src/shared/models.py`):

| Model | Key Validators |
|---|---|
| `RawMail` | EmailStr validation, HTTPS-only blob URLs (except localhost), non-empty transaction IDs |
| `EnrichedInvoice` | GL code = exactly 4 digits, vendor name trimmed/non-empty, amount > 0 and < $10M, currency in [USD, EUR, CAD] |
| `VendorMaster` | GL code format, vendor name normalization, lowercase RowKey |
| `InvoiceTransaction` | YYYYMM partition key (2020-2100 range), ErrorMessage required when Status='error' |
| `NotificationMessage` | Strict field validation |

*(models.py: `RawMail`, `EnrichedInvoice`, `VendorMaster`, `InvoiceTransaction`, `NotificationMessage` class definitions)*

### OData Injection Prevention

`src/shared/deduplication.py` defines `_sanitize_odata_string()` to escape single quotes before building Table Storage OData filters:

```python
def _sanitize_odata_string(value: str) -> str:
    return value.replace("'", "''")  # OData escaping
```

Applied to all deduplication queries via the `is_duplicate_message` and `is_duplicate_invoice` functions.

---

## 5. Application-Level Security Controls

### Webhook Security (MailWebhook)

**Client state validation** (MailWebhook/\_\_init\_\_.py: `clientState` comparison in notification processing loop):

- Every Graph API notification must include the correct `clientState` secret
- Invalid notifications are logged (with truncated secret) and skipped
- Returns 500 if `GRAPH_CLIENT_STATE` is not configured

**Validation handshake** (MailWebhook/\_\_init\_\_.py: `validationToken` handling block): URL-decodes and returns the Graph API validation token during subscription creation.

### Rate Limiting

IP-based rate limiting via Table Storage (`src/shared/rate_limiter.py`: `check_rate_limit()` and `get_client_ip()` functions):

| Endpoint | Limit | Auth Level |
|---|---|---|
| MailWebhook | 100 req/min | Anonymous (required for Graph API) |
| AddVendor | 10 req/min | Function key |
| Health | 60 req/min | Anonymous |

Client IP extracted from `X-Forwarded-For` or `X-Real-IP` headers. **Fail-open behavior**: if the rate limit check itself fails, the request proceeds (prevents false-positive blocking).

### Circuit Breakers

Three breakers protect against cascade failures (`src/shared/circuit_breaker.py`):

| Breaker | Failure Threshold | Reset Timeout | Excluded Exceptions |
|---|---|---|---|
| `graph_breaker` | 5 failures | 60 seconds | ValueError, KeyError |
| `openai_breaker` | 3 failures | 30 seconds | — |
| `storage_breaker` | 5 failures | 45 seconds | — |

### Email Loop Prevention

Four layers in `src/shared/email_processor.py` (filter functions) and `src/PostToAP/__init__.py` (recipient validation):

1. Skips emails FROM the system mailbox (self-sent)
2. Detects AP email format pattern (`DEPT / schedule SCHEDULE`)
3. Skips vendor registration reply emails
4. Validates recipient is NOT the ingest mailbox + whitelist check

### Deduplication

- **Message-level**: Checks Graph API message ID against InvoiceTransactions table (deduplication.py: `is_message_already_processed()` function)
- **Invoice-level**: SHA-256 hash of (vendor + sender + date), 90-day lookback window (deduplication.py: `check_duplicate_invoice()` function)
- Both are **fail-open** — if the dedup check fails, processing continues

### Error Handling & Information Leakage

- **Health endpoint**: Returns minimal response by default; detailed info only with `?detailed=true` (Health/\_\_init\_\_.py: response builder)
- **Webhook errors**: Logged server-side with full traceback at DEBUG level only (MailWebhookProcessor/\_\_init\_\_.py: exception handler)
- **Teams failures**: Non-critical, logged as warnings, don't affect main pipeline (Notify/\_\_init\_\_.py: webhook error handling)
- **Credential truncation**: Client state logged as first 8 chars only (MailWebhook/\_\_init\_\_.py: `clientState` logging)

### Poison Queue Handling

Azure Storage Queues retry failed messages up to **5 times**, then route to the corresponding poison queue. Each queue consumer validates messages with Pydantic's `model_validate_json()` and re-raises exceptions intentionally to trigger retry.

---

## 6. CI/CD Security

From `.github/workflows/ci-cd.yml`:

| Control | Section | Description |
|---|---|---|
| **Gitleaks** | `Scan for secrets with Gitleaks` step | Secret scanning on every commit |
| **Flake8** | `Lint with Flake8` step | Linting with max cyclomatic complexity 10 |
| **Black** | `Check code formatting with Black` step | Code formatting enforcement |
| **Test suite** | `Run unit and integration tests with coverage` step | 472 tests, 93% coverage, 85% minimum gate |
| **Prod dependency stripping** | `build` job: package assembly steps | Removes pytest, mypy, bandit from production package |
| **SAS URL masking** | `deploy-prod` job: `::add-mask::` commands | Account keys and SAS URLs masked in logs |
| **GitHub Secrets** | `deploy-prod` / `deploy-dev` jobs: `secrets.AZURE_CREDENTIALS_*` | Azure credentials stored as repository secrets only |
| **Bicep linting** | `deploy-prod` job: Bicep validation step | Infrastructure-as-code validation |
| **Health check** | `deploy-prod` job: post-deployment health verification | Verifies 200 status + 9 functions loaded |

### Security Scanning Tools

- **bandit**: Python security linter (`bandit -r src/`)
- **Gitleaks**: Prevents credential commits
- **mypy --strict**: Full type coverage catches unsafe patterns
- **Dependabot**: CVE monitoring for dependencies (e.g., requests >= 2.32.5 for CVE-2024-35195)

---

## 7. Operational Security Procedures

From `docs/operations/SECURITY_PROCEDURES.md`:

### Quarterly Access Reviews

- List all RBAC assignments, compare to expected baseline
- Key Vault access policy audit (only Function App MI + deployment SP + DevOps read-only)
- GitHub repository access cleanup

### Incident Response

| Priority | Trigger | Response Time |
|---|---|---|
| P1 | Credentials exposed | 1 hour — invalidate, audit, restart, document |
| P2 | Active exploitation | 4 hours — isolate, log, review, block |

### Vulnerability Patching SLAs

| CVSS | Timeline |
|---|---|
| 9-10 (Critical) | 24 hours |
| 7-8 (High) | 7 days |
| 4-6 (Medium) | 30 days |
| 0-3 (Low) | Regular updates |

### Compliance Posture

- Encryption at rest (Azure default)
- Encryption in transit (HTTPS/TLS 1.2)
- RBAC access controls
- Audit logging (Application Insights + Key Vault diagnostics)
- 7-year audit trail retention target
- Approved dependency list with license checks (no GPL/AGPL)

---

## 8. Security Architecture Summary

```
                              ┌─────────────────────────────────┐
                              │        Key Vault                │
                              │  9 secrets, soft delete,        │
                              │  purge protection, audit logs   │
                              │  Access: get/list only (MI)     │
                              └──────────┬──────────────────────┘
                                         │ @Microsoft.KeyVault() refs
                                         ▼
┌──────────────┐  HTTPS/TLS 1.2  ┌──────────────────────────────┐
│  Graph API   │◄────────────────│     Function App (Linux)     │
│  (OAuth 2.0) │  Bearer token   │  System-Assigned MI          │
└──────────────┘                 │  httpsOnly, FTPS disabled    │
                                 │  Rate limiting, circuit break │
                                 └──────────┬───────────────────┘
                                            │ Managed Identity (RBAC)
                                            ▼
                              ┌─────────────────────────────────┐
                              │      Storage Account            │
                              │  HTTPS only, TLS 1.2, no pub   │
                              │  Blob/Container soft delete     │
                              │  RBAC: Blob+Queue+Table Contrib │
                              └─────────────────────────────────┘
```

### Controls Count

| Layer | Controls |
|---|---|
| Identity & RBAC | 8 role assignments, 2 managed identities, 2 access policies |
| Secrets Management | 9 Key Vault secrets, rotation procedures, audit logging |
| Transport Security | HTTPS-only (Function + Storage), TLS 1.2, FTPS disabled, CORS locked |
| Data Protection | Blob/container soft delete, purge protection, public access disabled |
| Application Security | Rate limiting (3 endpoints), circuit breakers (3), dedup (2 layers), loop prevention (4 checks), Pydantic validation (5 models), OData injection prevention |
| CI/CD Security | Gitleaks, dependency stripping, SAS masking, health checks |
| Operational | Quarterly reviews, secret rotation (90/180 day), incident response, patching SLAs |

---

## Known Gaps (Accepted Risk, Documented)

1. **Storage/Key Vault network ACLs set to `Allow`** — mitigated by RBAC; VNet would require Premium plan (~$175/mo, Issue #72)
2. **MailWebhook is `authLevel: anonymous`** — required by Graph API webhook spec; mitigated by clientState validation + rate limiting
3. **Graph API Application Access Policy not yet deployed** — currently Mail.Read on all mailboxes; AAP to restrict to invoice mailbox documented in `MAIL_PERMISSIONS_GUIDE.md`
4. **Key Vault uses access policies, not Azure RBAC authorization** — `enableRbacAuthorization: false`; both methods provide equivalent security for this use case

---

## Related Documentation

- [Architecture](ARCHITECTURE.md) — System design and data flow
- [ADR-0010](adr/0010-managed-identity-auth.md) — Managed Identity decision
- [ADR-0031](adr/0031-azqr-security-recommendations.md) — AZQR Phase 1 recommendations
- [ADR-0034](adr/0034-blob-url-deployment.md) — Blob URL deployment pattern
- [Key Rotation](operations/KEY_ROTATION.md) — Secret rotation procedures
- [Security Procedures](operations/SECURITY_PROCEDURES.md) — Operational security runbook
- [Mail Permissions Guide](MAIL_PERMISSIONS_GUIDE.md) — Graph API permission model
