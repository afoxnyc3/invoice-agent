# Security Procedures

**Last Updated:** November 13, 2025

Security operations and compliance procedures for Invoice Agent. This guide covers secret rotation, access reviews, vulnerability management, and incident response.

## Table of Contents
- [Secret Rotation](#secret-rotation)
- [Access Review Process](#access-review-process)
- [Compliance Requirements](#compliance-requirements)
- [Vulnerability Management](#vulnerability-management)
- [Security Incident Response](#security-incident-response)
- [Dependency Management](#dependency-management)
- [Security Scanning](#security-scanning)

---

## Secret Rotation

### Rotation Schedule

| Secret | Type | Frequency | Owner | Last Rotated |
|--------|------|-----------|-------|--------------|
| Storage account key | Access key | 90 days | DevOps | 2025-11-01 |
| Service principal credential | Certificate | 365 days | DevOps | 2025-10-15 |
| Teams webhook URL | Integration | 180 days | Ops | 2025-11-01 |
| Graph API certificate | Certificate | 365 days | DevOps | 2025-10-15 |

### Storage Account Key Rotation

**Owner:** DevOps Engineer
**Duration:** 15 minutes
**Frequency:** Every 90 days

**Procedure:**

```bash
# 1. Generate new key (Azure automatically creates secondary)
# Go to Azure Portal → Storage Account → Access Keys
# OR use CLI:

az storage account keys renew \
  --account-name stinvoiceagentprod \
  --key primary \
  --resource-group rg-invoice-agent-prod

# Output: Shows old and new keys

# 2. Update in Key Vault (if used)
az keyvault secret set \
  --vault-name vault-invoice-agent \
  --name "StorageAccountKey" \
  --value "$(az storage account show-connection-string \
    --name stinvoiceagentprod -o tsv)"

# 3. Update Function App settings
NEW_CONN=$(az storage account show-connection-string \
  --name stinvoiceagentprod \
  --query connectionString -o tsv)

az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings AzureWebJobsStorage="$NEW_CONN"

# 4. Restart function app to apply changes
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 5. Verify functionality
curl -X POST https://func-invoice-agent-prod.azurewebsites.net/api/AddVendor \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Test",
    "vendor_domain": "test.com",
    "expense_dept": "IT",
    "gl_code": "9999",
    "allocation_schedule": "MONTHLY",
    "billing_party": "Test"
  }'

# Expected: 201 Created

# 6. Document rotation
echo "$(date): Storage key rotated" >> security_rotation_log.txt

# 7. Alert team
# Post in #invoice-agent-security: Storage key rotated successfully
```

**Verification:**
```bash
# Confirm all functions working
az monitor app-insights query \
  --app ai-invoice-agent-prod \
  --analytics-query "
    requests
    | where timestamp > ago(5m)
    | summarize errors = sumif(success == false)
  "

# Expected: 0 errors
```

**Rollback (If needed):**
```bash
# If new key doesn't work, revert to secondary
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings AzureWebJobsStorage="$(az storage account show-connection-string \
    --name stinvoiceagentprod --key secondary -o tsv)"

az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod
```

### Service Principal Certificate Rotation

**Owner:** DevOps Engineer
**Duration:** 30 minutes
**Frequency:** Every 365 days (or 30 days before expiry)

**Check Certificate Expiry:**
```bash
# List service principal credentials
az ad sp credential list \
  --id "service-principal-id" \
  --cert

# Look for "endDate" field
# If within 90 days: Time to rotate
```

**Rotation Procedure:**

```bash
# 1. Create new certificate
az ad sp credential reset \
  --name "sp-invoice-agent-prod" \
  --cert certificate.pem  # You provide a new certificate

# Or let Azure generate one (simpler):
az ad sp credential reset \
  --name "sp-invoice-agent-prod" \
  --create-cert  # Creates new cert in current directory

# Output: Includes new certificate thumbprint

# 2. Upload new certificate to Key Vault
NEW_THUMBPRINT="..."
az keyvault certificate import \
  --vault-name vault-invoice-agent \
  --name "GraphAPIServicePrincipal" \
  --file certificate.pem

# 3. Update Function App with new thumbprint
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings CERTIFICATE_THUMBPRINT="$NEW_THUMBPRINT"

# 4. Restart function app
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 5. Test Graph API access
# Monitor logs to verify authentication working

az functionapp log tail \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --timeout 60

# Expected: No "Unauthorized" errors

# 6. Remove old certificate (after 7 days grace period)
az ad sp credential delete \
  --id "service-principal-id" \
  --cert old_thumbprint

# 7. Document rotation
echo "$(date): Service principal certificate rotated" >> security_rotation_log.txt
```

### Teams Webhook Rotation

**Owner:** Ops Engineer
**Duration:** 10 minutes
**Frequency:** Every 180 days

**Procedure:**

```bash
# 1. Generate new webhook URL in Teams
# Go to: Teams Channel → Connectors → Incoming Webhook
# OR: Connectors → Manage → Add/Regenerate

# Copy the new webhook URL (includes unique token)

# 2. Update Function App setting
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings TEAMS_WEBHOOK_URL="https://outlook.webhook.office.com/..."

# 3. Test the new webhook
WEBHOOK=$(az functionapp config appsettings list \
  --name func-invoice-agent-prod \
  --query "[?name=='TEAMS_WEBHOOK_URL'].value" -o tsv)

curl -X POST "$WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d '{
    "@type": "MessageCard",
    "summary": "Security Test",
    "themeColor": "0078D4",
    "sections": [{
      "activityTitle": "Webhook Rotation Test",
      "text": "New webhook is working"
    }]
  }'

# Expected: HTTP 1 (success)

# 4. Delete old webhook in Teams
# Go back to Connectors → Remove old webhook

# 5. Document rotation
echo "$(date): Teams webhook rotated" >> security_rotation_log.txt
```

---

## Access Review Process

### Quarterly Access Review (Every 3 months)

**Owner:** Security Officer
**Duration:** 1-2 hours
**Schedule:** First week of Q2, Q3, Q4, Q1

**Procedure:**

```bash
# 1. List all users with Azure access
az role assignment list \
  --resource-group rg-invoice-agent-prod \
  --output table

# 2. Document who should have access
EXPECTED_ACCESS='{
  "DevOps Lead": "Contributor",
  "On-Call Engineer": "Contributor",
  "Developer 1": "Contributor",
  "Developer 2": "Contributor",
  "Read-Only Viewer": "Reader",
  "Security Team": "Reader"
}'

# 3. Compare actual vs expected
# Identify: Extra access, missing access, role mismatches

# 4. Remove unauthorized access
az role assignment delete \
  --assignee "user@company.com" \
  --role "Contributor" \
  --resource-group rg-invoice-agent-prod

# 5. Add missing access
az role assignment create \
  --assignee "new-user@company.com" \
  --role "Contributor" \
  --scope "/subscriptions/{sub}/resourceGroups/rg-invoice-agent-prod"

# 6. Document findings
cat > access_review_$(date +%Y%m%d).txt << EOF
Access Review - $(date)

Expected Users: $(echo $EXPECTED_ACCESS | jq '.keys | length')
Actual Users: $(az role assignment list --resource-group rg-invoice-agent-prod | jq '.length')
Discrepancies: [List any issues]

Actions Taken:
- Removed access for: [Names]
- Added access for: [Names]
- Role changes: [Details]

Approved by: [Name]
Date: $(date)
EOF
```

### Key Vault Access Review

```bash
# List Key Vault access policies
az keyvault access-policy list \
  --vault-name vault-invoice-agent \
  --resource-group rg-invoice-agent-prod

# Verify only these have access:
# - Function app managed identity
# - Deployment service principal
# - DevOps team members (read-only)

# Remove excess access
az keyvault access-policy delete \
  --vault-name vault-invoice-agent \
  --object-id "user-object-id"
```

### GitHub Repository Access

```bash
# List collaborators
gh repo collaborators list invoice-agent

# Expected: Only active developers
# Remove access for off-boarded team members

gh repo remove-collaborator invoice-agent "old-developer@company.com"
```

---

## Compliance Requirements

### Data Protection

**GDPR Compliance:**
- Invoice data may contain PII (vendor contact info)
- Data retention: 7 years (for accounting)
- Deletion: Follow retention policy

**Procedure:**
```bash
# Export vendor PII (if needed for GDPR request)
az storage entity query \
  --account-name stinvoiceagentprod \
  --table-name VendorMaster \
  --select "VendorName,ContactEmail" \
  --output json > vendor_data_export.json

# Delete on request
# Implement soft delete (Active flag) not hard delete
```

### Audit Logging

**Requirement:** All changes to critical data must be auditable

**Implementation:**
- Function App logs go to Application Insights
- Storage operations logged automatically
- Activity log captures infrastructure changes

**Retention:** 90 days minimum

**Verification:**
```bash
# Verify audit logging enabled
az functionapp config show \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --query "identity"

# Should show managed identity configured
```

### Security Baseline

**SOC 2 Type II Requirements:**
- ✅ Encryption at rest (Azure default)
- ✅ Encryption in transit (HTTPS only)
- ✅ Access controls (RBAC)
- ✅ Audit logging (Application Insights)
- ✅ Backup & recovery (30-day retention)
- ✅ Incident response plan (this document)

---

## Vulnerability Management

### Monthly Dependency Scan

**Owner:** DevOps Engineer
**Duration:** 30 minutes
**Schedule:** First Friday of month

**Procedure:**

```bash
# 1. Check for vulnerable packages
cd src
pip list --outdated

# 2. Generate security report
pip install safety
safety check

# Example output:
# [X] Package A has security vulnerability
# - Issue: Remote code execution
# - Fixed in version: X.X.X
# - Recommend: Update immediately

# 3. Update vulnerable packages
pip install --upgrade vulnerable-package>=X.X.X

# 4. Update requirements.txt
pip freeze > requirements.txt

# 5. Run tests
cd ..
pytest tests/unit tests/integration -v --cov

# Expected: All tests pass with new versions

# 6. Deploy if tests pass
# Create pull request with dependency updates

# 7. Document findings
cat > vulnerability_scan_$(date +%Y%m%d).txt << EOF
Vulnerability Scan - $(date)

Packages scanned: $(pip list | wc -l)
Vulnerabilities found: [N]
Critical: [N]
High: [N]
Medium: [N]
Low: [N]

Packages updated: [List]
Packages deferred: [List with reasons]

Tests: PASS
Deployment status: Ready/Deferred
EOF
```

### CVE Monitoring

**Subscribe to Security Advisories:**
```bash
# GitHub Dependabot alerts (automatic)
# Azure Security Advisories (check quarterly)

# View GitHub Dependabot alerts
gh repo view --json vulnerability
```

**Response Process:**
- Critical (CVSS 9-10): Patch within 24 hours
- High (CVSS 7-8): Patch within 7 days
- Medium (CVSS 4-6): Patch within 30 days
- Low (CVSS 0-3): Patch during regular updates

---

## Vulnerability Disclosure

**If you discover a vulnerability:**

1. **Do NOT** post publicly
2. **Email** security@company.com with:
   - Description of vulnerability
   - Steps to reproduce
   - Suggested fix (if known)
   - Your name and contact info

3. **Wait** for acknowledgment (within 24 hours)
4. **Coordinate** on patch timeline
5. **Follow** company responsible disclosure policy

---

## Security Incident Response

### Incident Classification

| Level | Example | Response Time | Severity |
|-------|---------|----------------|----------|
| P1 | Credentials exposed, data breach | 1 hour | Critical |
| P2 | Active exploitation, SLA violation | 4 hours | High |
| P3 | Vulnerability found, patch available | 1 week | Medium |
| P4 | Best practice gap, no active threat | 30 days | Low |

### P1 Incident Response (Credentials Exposed)

**Immediate Actions (Within 1 hour):**

```bash
# 1. Identify compromised credential
# (Storage key, API key, certificate, etc.)

# 2. Invalidate immediately
if storage_key_compromised; then
  az storage account keys regenerate \
    --account-name stinvoiceagentprod \
    --key primary \
    --resource-group rg-invoice-agent-prod
fi

# 3. Check for unauthorized access
az monitor activity-log list \
  --resource-group rg-invoice-agent-prod \
  --caller "compromised-account" \
  --start-time "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"

# 4. Restart affected service
az functionapp restart \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 5. Notify security team
# Slack: #security-incidents (with P1 tag)
# Include: What, When, Impact, Actions taken

# 6. Document incident
cat > incident_$(date +%Y%m%d_%H%M%S).txt << EOF
SECURITY INCIDENT - P1

What: Storage account key exposed in [logs/code/email]
When: Discovered $(date)
Duration: [Time from exposure to remediation]
Impact: Potential unauthorized access to [VendorMaster/blobs/etc]

Actions:
- [ ] Key regenerated
- [ ] Service restarted
- [ ] Logs reviewed for unauthorized access
- [ ] Incident reported to security team

Root Cause Analysis:
[To be completed within 24 hours]

Prevention:
- [ ] Implement secret scanning in CI/CD
- [ ] Update secret rotation frequency
- [ ] Train team on secret handling

Approval: [Security officer]
EOF
```

### P2 Incident Response (Active Exploitation)

```bash
# 1. Isolate affected function (if possible)
az functionapp function delete \
  --name AddVendor \
  --functionapp-name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod

# 2. Enable detailed logging
az functionapp config appsettings set \
  --name func-invoice-agent-prod \
  --resource-group rg-invoice-agent-prod \
  --settings LOGGING_LEVEL="DEBUG"

# 3. Capture traffic logs
# Enable Network Watcher, capture packets

# 4. Review access logs
az monitor activity-log list \
  --resource-group rg-invoice-agent-prod \
  --start-time "$(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --filter "eventTimestamp ge '2025-11-13T10:00:00Z' and eventTimestamp le '2025-11-13T16:00:00Z'"

# 5. Block suspicious IPs (if applicable)
# Update Azure Firewall rules

# 6. Notify stakeholders
```

### Post-Incident Actions

**Within 24 Hours:**
- [ ] Incident report completed
- [ ] Root cause identified
- [ ] Remediation actions taken
- [ ] Impact assessed

**Within 7 Days:**
- [ ] Security review conducted
- [ ] Preventive measures implemented
- [ ] Team training completed
- [ ] Incident closed

---

## Dependency Management

### Python Dependency Policy

**Approved Packages:**
```
# Core Azure
azure-functions
azure-data-tables
azure-storage-blob
azure-identity

# Email & Graph
msal
requests

# Data Validation
pydantic
email-validator

# Utilities
python-ulid

# Testing
pytest
pytest-cov
pytest-mock

# Quality
black
flake8
mypy
bandit
```

**Restricted Packages:**
- ❌ No web scraping frameworks (requests OK for APIs only)
- ❌ No data export to unauthorized services
- ❌ No cryptographic libraries (use built-in, Azure managed)

**Adding New Dependencies:**

```bash
# 1. Justify business need
# 2. Security review (check known CVEs)
pip install safety-check-package

# 3. License check (no GPL, AGPL)
pip install license

# 4. Add to requirements.txt
pip freeze | grep new-package >> requirements.txt

# 5. Test thoroughly
pytest -v

# 6. Code review approval
# 7. PR merge and deploy
```

---

## Security Scanning

### Pre-Commit Hook Security Scan

**Automatic on every commit:**

```bash
# .pre-commit-config.yaml includes:
- repo: https://github.com/PyCQA/bandit
  hooks:
  - id: bandit
    args: ['-r', 'src/']

- repo: https://github.com/Yelp/detect-secrets
  hooks:
  - id: detect-secrets
    args: ['scan']
```

### CI/CD Security Scanning

**Automated in GitHub Actions:**

```yaml
- name: Security Scan
  run: |
    bandit -r src/functions src/shared -f json -o bandit-report.json
    safety check --json > safety-report.json
    # Fail if any findings
```

---

## Security Checklist

**For Security Officer (Monthly):**
- [ ] Vulnerability scan completed
- [ ] No P1/P2 incidents in last month
- [ ] Access review current (quarterly)
- [ ] Secret rotation on schedule
- [ ] Audit logs reviewed for anomalies
- [ ] Backup security verified
- [ ] Team training current

**For DevOps (Quarterly):**
- [ ] Security baseline review
- [ ] Compliance status confirmed
- [ ] DR security test passed
- [ ] Network security policies reviewed
- [ ] Certificate expiries checked
- [ ] Firewall rules current

**For Developers (Before Each PR):**
- [ ] No hardcoded secrets
- [ ] No sensitive data in logs
- [ ] Input validation complete
- [ ] OWASP top 10 considered
- [ ] Unit tests for security features
- [ ] Code review by peer

---

## Contact & Escalation

**Security Team:** security@company.com
**CISO:** [Name]
**Incident Line:** [Phone/Slack]

**On-Call Security:** Slack #invoice-agent-security

---

**See Also:**
- [Disaster Recovery](DISASTER_RECOVERY.md) - Security incident response
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Authentication errors
- [CLAUDE.md](../CLAUDE.md) - Project constraints & security requirements
