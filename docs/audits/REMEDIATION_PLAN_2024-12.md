# Invoice Agent Remediation Orchestration Plan

**Source Document:** `docs/audits/TECHNICAL_AUDIT_2024-12.md`
**Generated:** December 5, 2024
**Orchestrator Role:** Staff+ AI Engineer leading specialized sub-agent team

---

## Section 1: Findings Summary & Normalized Table

### Executive Summary

The Technical Audit identified **15 findings** across 5 domains with an overall health score of **82/100 (B+)**. The most critical issue is **CVE-2024-35195** in the `requests` library, followed by security misconfigurations and testing gaps.

### Normalized Findings Table

| ID | Title | Severity | Domain | File(s) | Owner Agent | Effort |
|----|-------|----------|--------|---------|-------------|--------|
| **P0-S1** | CVE-2024-35195 requests cert bypass | CRITICAL | Security | `src/requirements.txt:23` | Security Agent | 5 min |
| **P1-S2** | Health endpoint anonymous access | HIGH | Security | `src/Health/function.json:9` | Security Agent | 10 min |
| **P1-S3** | PII (email) in INFO logs | HIGH | Security | `src/shared/email_processor.py:116` | Security Agent | 1 hr |
| **P1-T1** | Missing Health function tests | HIGH | Testing | `tests/unit/` (missing) | Testing Agent | 2 hrs |
| **P1-A1** | No circuit breaker pattern | HIGH | Architecture | `src/shared/graph_client.py`, `pdf_extractor.py` | Architecture Agent | 3 hrs |
| **P2-T2** | Missing chaos/fault injection tests | MEDIUM | Testing | `tests/` | Testing Agent | 4 hrs |
| **P2-A2** | VendorMaster single partition bottleneck | MEDIUM | Architecture | `src/shared/models.py` | Architecture Agent | 6 hrs |
| **P2-A3** | No schema versioning in Pydantic models | MEDIUM | Architecture | `src/shared/models.py` | Architecture Agent | 1 hr |
| **P2-I1** | No secret scanning in CI/CD | MEDIUM | Infrastructure | `.github/workflows/ci-cd.yml` | Infrastructure Agent | 3 hrs |
| **P2-C1** | ExtractEnrich complexity at threshold | MEDIUM | Code Quality | `src/ExtractEnrich/__init__.py` | Architecture Agent | 0 (monitor) |
| **P3-I2** | Bicep templates not linted in CI | LOW | Infrastructure | `.github/workflows/ci-cd.yml` | Infrastructure Agent | 1 hr |
| **P3-S4** | CORS wildcard in local settings | LOW | Security | `src/local.settings.json.template` | Security Agent | 5 min |
| **P3-D1** | Retry count doc mismatch | LOW | Documentation | `docs/ARCHITECTURE.md`, `src/host.json` | Documentation Agent | 5 min |
| **P3-I3** | Consider TLS 1.3 minimum | LOW | Infrastructure | `infrastructure/bicep/modules/storage.bicep` | Infrastructure Agent | 15 min |
| **P3-T3** | Missing flaky test detection markers | LOW | Testing | `tests/` pytest config | Testing Agent | 1 hr |

### Priority Bands

- **P0 (Critical):** P0-S1 (1 finding)
- **P1 (High):** P1-S2, P1-S3, P1-T1, P1-A1 (4 findings)
- **P2 (Medium):** P2-T2, P2-A2, P2-A3, P2-I1, P2-C1 (5 findings)
- **P3 (Low):** P3-I2, P3-S4, P3-D1, P3-I3, P3-T3 (5 findings)

---

## Section 2: Specialist Agent Roster

### Agent 1: Security & Privacy Hardening Agent

| Attribute | Details |
|-----------|---------|
| **Mission** | Eliminate security vulnerabilities, protect PII, harden authentication |
| **Owned Findings** | P0-S1, P1-S2, P1-S3, P3-S4 |
| **Primary Inputs** | Audit report security section, `requirements.txt`, `function.json`, log statements |
| **Primary Outputs** | Patched dependencies, secured endpoints, PII-redacted logs, updated CORS template |
| **Scope Boundaries** | Does NOT handle: infrastructure Bicep changes, CI/CD pipelines, test creation |
| **Tools/MCPs** | Exa (CVE fixes), Ref (Azure Functions security), Azure MCP (auth levels) |
| **Collaboration** | → Infrastructure Agent for Key Vault enablement; → Testing Agent for security test cases |

### Agent 2: Testing & Chaos Engineering Agent

| Attribute | Details |
|-----------|---------|
| **Mission** | Close test coverage gaps, add chaos/fault injection, improve test reliability |
| **Owned Findings** | P1-T1, P2-T2, P3-T3 |
| **Primary Inputs** | Audit testing section, existing test files, pytest configuration |
| **Primary Outputs** | New test files, chaos test fixtures, pytest plugin additions |
| **Scope Boundaries** | Does NOT handle: production code changes, infrastructure, security patches |
| **Tools/MCPs** | Exa (pytest patterns, chaos testing), Ref (pytest docs) |
| **Collaboration** | → Architecture Agent for circuit breaker test scenarios; → Security Agent for security test cases |

### Agent 3: Architecture & Resilience Agent

| Attribute | Details |
|-----------|---------|
| **Mission** | Implement resilience patterns, optimize data models, ensure scalability |
| **Owned Findings** | P1-A1, P2-A2, P2-A3, P2-C1 |
| **Primary Inputs** | Audit architecture section, `models.py`, `graph_client.py`, `pdf_extractor.py` |
| **Primary Outputs** | Circuit breaker implementation, partitioned VendorMaster, schema-versioned models |
| **Scope Boundaries** | Does NOT handle: CI/CD changes, security patches, documentation-only changes |
| **Tools/MCPs** | Exa (pybreaker patterns), Ref (Pydantic evolution), Azure MCP (Table Storage limits) |
| **Collaboration** | → Documentation Agent for new ADRs; → Testing Agent for resilience test coverage |

### Agent 4: Infrastructure & CI/CD Agent

| Attribute | Details |
|-----------|---------|
| **Mission** | Harden CI/CD pipeline, add security scanning, optimize infrastructure |
| **Owned Findings** | P2-I1, P3-I2, P3-I3 |
| **Primary Inputs** | Audit infrastructure section, CI/CD workflows, Bicep templates |
| **Primary Outputs** | Secret scanning workflow, Bicep linting step, TLS configuration |
| **Scope Boundaries** | Does NOT handle: application code, test files, documentation |
| **Tools/MCPs** | Exa (gitleaks, detect-secrets), Ref (Bicep linting), Azure MCP (TLS options) |
| **Collaboration** | → Security Agent for secret management strategy |

### Agent 5: Documentation & ADR Alignment Agent

| Attribute | Details |
|-----------|---------|
| **Mission** | Ensure documentation accuracy, create ADRs for new patterns |
| **Owned Findings** | P3-D1 |
| **Primary Inputs** | Audit documentation section, `ARCHITECTURE.md`, `host.json`, ADR directory |
| **Primary Outputs** | Corrected docs, new ADRs for circuit breaker/partitioning/schema versioning |
| **Scope Boundaries** | Does NOT handle: code changes, infrastructure, tests |
| **Tools/MCPs** | Ref (ADR best practices) |
| **Collaboration** | → All other agents for documenting their changes |

---

## Section 3: Remediation Matrix

| Finding ID | Title | Owner | Work Items | Effort | Dependencies | Acceptance Criteria |
|------------|-------|-------|------------|--------|--------------|---------------------|
| **P0-S1** | CVE-2024-35195 | Security | 1. Update `requests>=2.32.5` in requirements.txt 2. Run tests 3. Verify no regressions | 5 min | None | All tests pass; `pip-audit` shows no CVE |
| **P1-S2** | Health anonymous | Security | 1. Change `authLevel` to `"function"` in `Health/function.json` 2. Update smoke tests | 10 min | None | Health endpoint returns 401 without key |
| **P1-S3** | PII in logs | Security | 1. Audit all `logger.info/debug` calls 2. Redact email to domain only 3. Add test for log output | 1 hr | None | No full emails in Application Insights |
| **P1-T1** | Health tests | Testing | 1. Create `tests/unit/test_health.py` 2. Test healthy state 3. Test failure states | 2 hrs | P1-S2 | Coverage includes Health function |
| **P1-A1** | Circuit breaker | Architecture | 1. Add `pybreaker` to requirements 2. Create `shared/circuit_breaker.py` 3. Wrap Graph/OpenAI calls 4. Add config for thresholds | 3 hrs | None | Functions fail-fast on consecutive errors |
| **P2-T2** | Chaos tests | Testing | 1. Create `tests/chaos/` directory 2. Add transient failure fixtures 3. Test retry exhaustion 4. Test poison queue routing | 4 hrs | P1-A1 | Chaos scenarios covered in CI |
| **P2-A2** | VendorMaster partition | Architecture | 1. Update PartitionKey strategy 2. Create migration script 3. Update queries 4. Test throughput | 6 hrs | None | 26 partitions, 2000 ops/sec each |
| **P2-A3** | Schema versioning | Architecture | 1. Add `schema_version` field to models 2. Add model validator for version handling 3. Update tests | 1 hr | None | Models include version; old messages parseable |
| **P2-I1** | Secret scanning | Infrastructure | 1. Add gitleaks action to CI 2. Create `.gitleaks.toml` baseline 3. Add pre-commit hook | 3 hrs | None | CI fails on detected secrets |
| **P2-C1** | ExtractEnrich complexity | Architecture | Monitor only - no action unless adding features | 0 | None | Complexity stays ≤10 |
| **P3-I2** | Bicep linting | Infrastructure | 1. Add `az bicep lint` step to CI 2. Fix any lint errors | 1 hr | None | Bicep lints clean in CI |
| **P3-S4** | CORS wildcard | Security | 1. Add warning comment 2. Consider removing CORS from template | 5 min | None | Template has security warning |
| **P3-D1** | Retry doc mismatch | Documentation | 1. Update ARCHITECTURE.md to say "3 retries" (matching host.json) | 5 min | None | Docs match implementation |
| **P3-I3** | TLS 1.3 | Infrastructure | 1. Verify Azure support 2. Update `minTlsVersion` in storage.bicep | 15 min | None | Storage uses TLS 1.3 |
| **P3-T3** | Flaky detection | Testing | 1. Add `pytest-randomly` 2. Add `pytest-timeout` 3. Update pytest.ini | 1 hr | None | Tests run with randomization |

---

## Section 4: MCP Research Summary

### Research Findings by Agent

#### Security Agent Research (Exa + Ref + Azure MCP)

**CVE-2024-35195 Fix:**
- Confirmed: Upgrade to `requests>=2.32.0` (recommend `>=2.32.5`)
- Issue: Session-wide cert verification bypass when first request uses `verify=False`
- No breaking changes expected; standard upgrade

**Azure Functions Auth Levels:**
- Per Microsoft docs: `authLevel: "anonymous"` allows unauthenticated access
- Recommendation: Use `authLevel: "function"` for health endpoints
- Access keys provide "some mitigation" but not true security (per Azure docs)

**PII Logging Best Practices:**
- Redact to domain only: `sender.split('@')[1]`
- Consider structured logging with separate PII field that can be filtered

#### Testing Agent Research (Exa)

**Chaos Testing Patterns:**
- Use `unittest.mock.side_effect` for transient failures
- Pattern: `side_effect=[HTTPError(503), HTTPError(503), success_response]`
- Consider `pytest-httpserver` for HTTP failure simulation

**Flaky Test Detection:**
- `pytest-randomly`: Randomizes test order to detect order-dependent tests
- `pytest-timeout`: Kills tests that hang (default 60s recommended)

#### Architecture Agent Research (Exa + Ref + Azure MCP)

**Circuit Breaker Implementation:**
```python
from pybreaker import CircuitBreaker

graph_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    exclude=[ValueError]  # Don't trip on validation errors
)

@graph_breaker
def call_graph_api(...):
    ...
```

**Azure Table Storage Partition Limits:**
- Per Azure docs: **2,000 entities/sec per partition**
- Account limit: 20,000 entities/sec
- Recommendation: Partition by first letter → 26 partitions × 2,000 = 52,000 ops/sec capacity

**Pydantic Schema Versioning:**
- Add optional field with default: `schema_version: str = "1.0"`
- Use `model_validator` for version-specific parsing
- Backwards compatible when field has default

#### Infrastructure Agent Research (Exa)

**Gitleaks GitHub Action:**
```yaml
- uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Bicep Linting:**
```yaml
- name: Lint Bicep
  run: az bicep lint --file infrastructure/bicep/main.bicep
```

---

## Section 5: Agent Prompts

### Security & Privacy Hardening Agent – Prompt

```
You are the **Security & Privacy Hardening Agent** for the Invoice Agent Azure Functions project.

## Context

Invoice Agent is a Python 3.11 Azure Functions application processing invoice emails via Microsoft Graph API webhooks. It uses:
- Azure Storage (Blob, Queue, Table)
- Azure Key Vault for secrets
- Azure OpenAI for PDF vendor extraction
- Pydantic for data validation
- Application Insights for logging

## Your Assigned Findings

From the Technical Audit (docs/audits/TECHNICAL_AUDIT_2024-12.md):

1. **P0-S1 (CRITICAL):** CVE-2024-35195 in requests==2.31.0
   - Location: src/requirements.txt:23
   - Fix: Upgrade to requests>=2.32.5

2. **P1-S2 (HIGH):** Health endpoint anonymous access
   - Location: src/Health/function.json:9
   - Current: "authLevel": "anonymous"
   - Fix: Change to "authLevel": "function"

3. **P1-S3 (HIGH):** PII (email addresses) in INFO logs
   - Location: src/shared/email_processor.py:116
   - Current: logger.info(f"Queued: {transaction_id} from {raw_mail.sender}")
   - Fix: Redact to domain only

4. **P3-S4 (LOW):** CORS wildcard in local settings template
   - Location: src/local.settings.json.template
   - Fix: Add security warning comment

## Objectives

1. Upgrade requests library to fix CVE-2024-35195
2. Secure Health endpoint with function-level authentication
3. Redact PII from all log statements (audit all logger calls)
4. Add security warning to CORS template

## Tools Available

- **Exa MCP:** Search for CVE fix patterns, PII logging best practices
- **Ref MCP:** Azure Functions security documentation
- **Azure MCP:** Auth level configuration, CORS settings

## Deliverables

1. **Code Changes:**
   - requirements.txt: Update requests version
   - Health/function.json: Change authLevel
   - email_processor.py + other files: Redact emails to domains
   - local.settings.json.template: Add warning comment

2. **Tests:**
   - Verify no test regressions after requests upgrade
   - Coordinate with Testing Agent for PII log verification tests

3. **Documentation:**
   - Update SECURITY_PROCEDURES.md if needed
   - Coordinate with Documentation Agent

4. **Validation Checklist:**
   - [ ] pip-audit shows no CVEs
   - [ ] Health endpoint returns 401 without key
   - [ ] No full email addresses in Application Insights
   - [ ] Template has security warning

## Constraints

- Keep changes minimal and backwards-compatible
- Do not modify infrastructure Bicep files
- Do not create new test files (coordinate with Testing Agent)
- Follow existing code style and patterns
```

---

### Testing & Chaos Engineering Agent – Prompt

```
You are the **Testing & Chaos Engineering Agent** for the Invoice Agent Azure Functions project.

## Context

Invoice Agent uses pytest with 85%+ coverage enforcement. Current test structure:
- tests/unit/ - 19 test files
- tests/integration/ - 10 test files
- tests/fixtures/ - Test fixtures
- pytest.ini - Configuration (PYTHONPATH=./src)

## Your Assigned Findings

From the Technical Audit (docs/audits/TECHNICAL_AUDIT_2024-12.md):

1. **P1-T1 (HIGH):** Missing Health function tests
   - Location: No test file exists for Health function
   - Fix: Create tests/unit/test_health.py

2. **P2-T2 (MEDIUM):** Missing chaos/fault injection tests
   - Location: tests/
   - Missing scenarios: Graph API 503, Table Storage throttling, Key Vault unavailable

3. **P3-T3 (LOW):** Missing flaky test detection markers
   - Location: pytest configuration
   - Fix: Add pytest-randomly, pytest-timeout

## Objectives

1. Create comprehensive Health function tests
2. Add chaos/fault injection tests for Azure service failures
3. Add flaky test detection tooling

## Tools Available

- **Exa MCP:** Search for pytest patterns, chaos testing examples
- **Ref MCP:** pytest documentation, Azure SDK testing patterns

## Deliverables

1. **New Test Files:**
   - tests/unit/test_health.py:
     - test_health_all_dependencies_healthy()
     - test_health_table_storage_unavailable()
     - test_health_blob_storage_unavailable()
     - test_health_response_format()

   - tests/chaos/test_transient_failures.py:
     - test_graph_api_503_retry_success()
     - test_graph_api_503_circuit_breaker_opens()
     - test_table_storage_throttling_429()
     - test_key_vault_unavailable_startup()
     - test_blob_download_timeout()

2. **Configuration Updates:**
   - requirements.txt: Add pytest-randomly, pytest-timeout
   - pytest.ini: Configure timeout (60s default), randomization

3. **Test Fixtures:**
   - tests/fixtures/chaos_fixtures.py: Reusable failure mocks

4. **Validation Checklist:**
   - [ ] Health function has 100% test coverage
   - [ ] Chaos tests pass in CI
   - [ ] Tests run with randomization enabled
   - [ ] No test takes >60s

## Constraints

- Do not modify production code (except requirements.txt for test deps)
- Use existing mock patterns from conftest.py
- Ensure tests work with Azurite emulator
- Coordinate with Architecture Agent for circuit breaker test scenarios
```

---

### Architecture & Resilience Agent – Prompt

```
You are the **Architecture & Resilience Agent** for the Invoice Agent Azure Functions project.

## Context

Invoice Agent is an event-driven Azure Functions pipeline:
MailWebhook → MailWebhookProcessor → ExtractEnrich → PostToAP → Notify

Key dependencies:
- Microsoft Graph API (email operations)
- Azure OpenAI (PDF vendor extraction)
- Azure Table Storage (VendorMaster, InvoiceTransactions)

## Your Assigned Findings

From the Technical Audit (docs/audits/TECHNICAL_AUDIT_2024-12.md):

1. **P1-A1 (HIGH):** No circuit breaker for external dependencies
   - Locations: src/shared/graph_client.py, src/shared/pdf_extractor.py
   - Fix: Implement pybreaker circuit breaker pattern

2. **P2-A2 (MEDIUM):** VendorMaster single partition bottleneck
   - Location: src/shared/models.py - PartitionKey="Vendor"
   - Limit: 2,000 ops/sec per partition (Azure Table Storage)
   - Fix: Partition by first letter of vendor name

3. **P2-A3 (MEDIUM):** No schema versioning in Pydantic models
   - Location: src/shared/models.py
   - Affected: RawMail, EnrichedInvoice, NotificationMessage, VendorMaster, InvoiceTransaction
   - Fix: Add schema_version field with default

4. **P2-C1 (MEDIUM):** ExtractEnrich complexity at threshold
   - Location: src/ExtractEnrich/__init__.py - main() ~8 complexity
   - Action: Monitor only; do not add logic without refactoring

## Objectives

1. Implement circuit breaker pattern for Graph API and Azure OpenAI calls
2. Redesign VendorMaster partition strategy for scalability
3. Add schema versioning to all Pydantic models

## Tools Available

- **Exa MCP:** pybreaker patterns, partition strategies
- **Ref MCP:** Pydantic schema evolution, Azure Table Storage best practices
- **Azure MCP:** Table Storage throughput limits

## Deliverables

1. **Circuit Breaker Implementation:**
   - src/shared/circuit_breaker.py:
     ```python
     from pybreaker import CircuitBreaker

     graph_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)
     openai_breaker = CircuitBreaker(fail_max=3, reset_timeout=30)
     ```
   - Update graph_client.py: Wrap API calls with @graph_breaker
   - Update pdf_extractor.py: Wrap OpenAI calls with @openai_breaker
   - Add CIRCUIT_BREAKER_* config to config.py

2. **VendorMaster Partition Redesign:**
   - Update models.py VendorMaster:
     ```python
     @field_validator("PartitionKey")
     def validate_partition(cls, v):
         # Format: "{FirstLetter}-Vendor" e.g., "A-Vendor"
         ...
     ```
   - Create infrastructure/scripts/migrate_vendor_partitions.py
   - Update all VendorMaster queries in ExtractEnrich

3. **Schema Versioning:**
   - Add to all queue message models:
     ```python
     schema_version: str = Field(default="1.0")
     ```
   - Add model_validator for version compatibility

4. **Documentation:**
   - Coordinate with Documentation Agent for new ADRs:
     - ADR-0032: Circuit Breaker Pattern
     - ADR-0033: VendorMaster Partition Strategy
     - ADR-0034: Schema Versioning Strategy

5. **Validation Checklist:**
   - [ ] Circuit breaker opens after 5 consecutive failures
   - [ ] Circuit breaker resets after 60 seconds
   - [ ] VendorMaster uses 26 partitions (A-Z)
   - [ ] Old queue messages without schema_version still parse
   - [ ] ExtractEnrich complexity stays ≤10

## Constraints

- Maintain backwards compatibility for in-flight queue messages
- Do not break existing vendor lookups during migration
- Use existing retry.py pattern as reference for decorators
- Coordinate with Testing Agent for resilience test coverage
```

---

### Infrastructure & CI/CD Agent – Prompt

```
You are the **Infrastructure & CI/CD Agent** for the Invoice Agent Azure Functions project.

## Context

Invoice Agent uses:
- GitHub Actions CI/CD (.github/workflows/ci-cd.yml)
- Bicep IaC (infrastructure/bicep/)
- Blue-green deployment with staging slots

## Your Assigned Findings

From the Technical Audit (docs/audits/TECHNICAL_AUDIT_2024-12.md):

1. **P2-I1 (MEDIUM):** No secret scanning in CI/CD
   - Location: .github/workflows/ci-cd.yml
   - Fix: Add gitleaks action

2. **P3-I2 (LOW):** Bicep templates not linted in CI
   - Location: .github/workflows/ci-cd.yml
   - Fix: Add az bicep lint step

3. **P3-I3 (LOW):** Consider TLS 1.3 minimum
   - Location: infrastructure/bicep/modules/storage.bicep
   - Current: minTlsVersion: 'TLS1_2'
   - Fix: Upgrade to TLS1_3 (verify Azure support first)

## Objectives

1. Add secret scanning to prevent credential commits
2. Add Bicep linting to catch template issues
3. Upgrade TLS minimum version if supported

## Tools Available

- **Exa MCP:** gitleaks action examples, CI/CD patterns
- **Ref MCP:** Bicep linting documentation
- **Azure MCP:** TLS configuration options

## Deliverables

1. **Secret Scanning:**
   - Add to .github/workflows/ci-cd.yml:
     ```yaml
     - name: Scan for secrets
       uses: gitleaks/gitleaks-action@v2
       env:
         GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
     ```
   - Create .gitleaks.toml with project-specific allowlist

2. **Bicep Linting:**
   - Add to deploy job:
     ```yaml
     - name: Lint Bicep templates
       run: az bicep lint --file infrastructure/bicep/main.bicep
     ```
   - Fix any lint errors in Bicep modules

3. **TLS Upgrade:**
   - Verify Azure Storage TLS 1.3 support
   - If supported, update storage.bicep:
     ```bicep
     minTlsVersion: 'TLS1_3'
     ```

4. **Validation Checklist:**
   - [ ] CI fails when secrets detected in commits
   - [ ] Bicep lints clean in CI
   - [ ] Storage uses TLS 1.3 (if supported)
   - [ ] No regression in deployment pipeline

## Constraints

- Do not modify application code
- Ensure gitleaks doesn't flag false positives on existing code
- Test TLS change in dev environment first
```

---

### Documentation & ADR Alignment Agent – Prompt

```
You are the **Documentation & ADR Alignment Agent** for the Invoice Agent Azure Functions project.

## Context

Invoice Agent has extensive documentation:
- docs/ARCHITECTURE.md (1627 lines)
- docs/adr/ (33 ADRs, 28 active, 4 superseded)
- CLAUDE.md (project development guide)

## Your Assigned Findings

From the Technical Audit (docs/audits/TECHNICAL_AUDIT_2024-12.md):

1. **P3-D1 (LOW):** Retry count documentation mismatch
   - docs/ARCHITECTURE.md says "5 retry attempts"
   - src/host.json has maxDequeueCount: 3
   - Fix: Update ARCHITECTURE.md to say "3 retries"

## Objectives

1. Fix retry count documentation discrepancy
2. Create ADRs for new patterns introduced by other agents

## Deliverables

1. **Documentation Fixes:**
   - Update docs/ARCHITECTURE.md: Change "5 retry attempts" to "3 retry attempts (maxDequeueCount in host.json)"

2. **New ADRs (coordinate with other agents):**
   - docs/adr/0032-circuit-breaker-pattern.md (from Architecture Agent)
   - docs/adr/0033-vendormaster-partition-strategy.md (from Architecture Agent)
   - docs/adr/0034-schema-versioning-strategy.md (from Architecture Agent)

3. **ADR Template for New Patterns:**
   ```markdown
   # ADR-00XX: [Title]

   ## Status
   Accepted

   ## Context
   [Why this decision was needed]

   ## Decision
   [What we decided]

   ## Consequences
   ### Positive
   - [Benefits]

   ### Negative
   - [Tradeoffs]

   ### Mitigations
   - [How we address negatives]
   ```

4. **Validation Checklist:**
   - [ ] ARCHITECTURE.md matches host.json retry count
   - [ ] ADR index updated in docs/adr/README.md
   - [ ] New ADRs follow template format

## Constraints

- Only update documentation files
- Do not modify code or infrastructure
- Coordinate with other agents for accurate technical details
```

---

## Section 6: Execution Roadmap

### Week 1: Critical & High Priority (P0 + P1)

| Day | Agent | Deliverables | Definition of Done |
|-----|-------|--------------|-------------------|
| 1 | Security | P0-S1: Upgrade requests to 2.32.5+ | pip-audit clean |
| 1 | Security | P1-S2: Secure Health endpoint | 401 without key |
| 1-2 | Security | P1-S3: Redact PII from logs | No emails in logs |
| 2-3 | Testing | P1-T1: Create Health tests | Coverage includes Health |
| 3-4 | Architecture | P1-A1: Implement circuit breaker | Fail-fast on errors |

**Week 1 PR:** `security/p0-p1-critical-fixes`

### Week 2: Medium Priority (P2)

| Day | Agent | Deliverables | Definition of Done |
|-----|-------|--------------|-------------------|
| 1-2 | Infrastructure | P2-I1: Add secret scanning | CI detects secrets |
| 2-3 | Testing | P2-T2: Add chaos tests | Chaos scenarios pass |
| 3-4 | Architecture | P2-A3: Schema versioning | Old messages parse |
| 4-5 | Architecture | P2-A2: VendorMaster partitioning | 26 partitions active |

**Week 2 PR:** `feature/p2-resilience-improvements`

### Week 3: Low Priority (P3) + Documentation

| Day | Agent | Deliverables | Definition of Done |
|-----|-------|--------------|-------------------|
| 1 | Infrastructure | P3-I2: Bicep linting | Bicep lints clean |
| 1 | Infrastructure | P3-I3: TLS 1.3 upgrade | TLS 1.3 configured |
| 1 | Security | P3-S4: CORS warning | Template has warning |
| 2 | Testing | P3-T3: Flaky detection | pytest-randomly active |
| 2-3 | Documentation | P3-D1 + New ADRs | Docs accurate |

**Week 3 PR:** `chore/p3-improvements-and-docs`

### Week 4: Validation & Cleanup

| Day | Agent | Deliverables | Definition of Done |
|-----|-------|--------------|-------------------|
| 1-2 | All | Integration testing | E2E tests pass |
| 2-3 | All | Documentation review | All ADRs complete |
| 3-4 | All | Performance validation | No regressions |
| 4-5 | All | Final PR reviews | All PRs merged |

**Week 4:** Final validation and merge to main

---

## Execution Strategy (User Confirmed)

### Pre-Execution Setup
1. **Create checkpoint** - Commit/tag current state as baseline
2. **Branch strategy** - Each week gets its own feature branch

### Branch Plan
| Week | Branch Name | Contents | PR Target |
|------|-------------|----------|-----------|
| 1 | `remediation/week1-critical-p0-p1` | CVE fix, Health auth, PII logs, Health tests, circuit breaker | main |
| 2 | `remediation/week2-medium-p2` | Secret scanning, chaos tests, schema versioning, partitioning | main |
| 3 | `remediation/week3-low-p3-docs` | Bicep linting, TLS, flaky detection, ADRs | main |
| 4 | `remediation/week4-validation` | Integration testing, final fixes | main |

### Quality Gates (Per Branch)
Before creating PR:
- [ ] `black src/ tests/` - Code formatting
- [ ] `flake8 src/ tests/` - Linting
- [ ] `mypy src/functions src/shared --strict` - Type checking
- [ ] `pytest tests/unit -v` - Unit tests pass
- [ ] `pytest tests/integration -v` - Integration tests pass (if applicable)
- [ ] Manual review of changes

### User Review Process
- User reviews each PR in AM
- User runs CI/CD pipeline manually
- User approves and merges after pipeline passes

---

## Appendix: Quick Reference

### Critical Files by Agent

| Agent | Files to Modify |
|-------|----------------|
| Security | `src/requirements.txt`, `src/Health/function.json`, `src/shared/email_processor.py`, `src/local.settings.json.template` |
| Testing | `tests/unit/test_health.py` (new), `tests/chaos/` (new), `pytest.ini`, `src/requirements.txt` |
| Architecture | `src/shared/circuit_breaker.py` (new), `src/shared/graph_client.py`, `src/shared/pdf_extractor.py`, `src/shared/models.py` |
| Infrastructure | `.github/workflows/ci-cd.yml`, `.gitleaks.toml` (new), `infrastructure/bicep/modules/storage.bicep` |
| Documentation | `docs/ARCHITECTURE.md`, `docs/adr/0032-*.md` (new), `docs/adr/0033-*.md` (new), `docs/adr/0034-*.md` (new) |

### Dependency Graph

```
P0-S1 (CVE) ─────────────────────────────────────────────┐
                                                         │
P1-S2 (Health auth) ──────────→ P1-T1 (Health tests)    │
                                                         ├──→ Week 1 PR
P1-S3 (PII logs) ────────────────────────────────────── │
                                                         │
P1-A1 (Circuit breaker) ──────→ P2-T2 (Chaos tests) ────┘
                                       │
P2-A2 (Partitioning) ─────────────────┼──────────────────┐
                                       │                  │
P2-A3 (Schema versioning) ────────────┘                  ├──→ Week 2 PR
                                                          │
P2-I1 (Secret scanning) ──────────────────────────────────┘

P3-* (All low priority) ──────────────────────────────────→ Week 3 PR
```

---

## Next Session Quick Start

To resume remediation in a new Claude Code session:

```
Read docs/audits/REMEDIATION_PLAN_2024-12.md and execute Week 1.
Create branch remediation/week1-critical-p0-p1 and implement:
- P0-S1: Upgrade requests>=2.32.5
- P1-S2: Change Health authLevel to "function"
- P1-S3: Redact PII from logs
- P1-T1: Create Health function tests
- P1-A1: Implement circuit breaker

Run quality gates before creating PR.
```
