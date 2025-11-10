# Change Log

All notable changes to the Invoice Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and documentation
- Azure Function scaffolding for 4 core functions
- Pydantic models for data validation
- Key Vault integration for secret management
- Sub-agents for automated code generation
- Slash commands for development workflow

### Changed
- Simplified Teams integration (webhooks only, no bot framework)
- Removed approval workflow (handled by NetSuite downstream)
- Streamlined scope for rapid MVP delivery

### Technical Decisions
- Chose Azure Functions over Container Apps for serverless benefits
- Selected Table Storage over Cosmos DB for cost efficiency
- Implemented ULID for transaction IDs instead of GUIDs
- Enforced 25-line function limit for maintainability

---

## [0.1.0] - 2024-11-09

### Added
- Project initialization
- `.claude/` directory with AI automation tools
  - CLAUDE.md - AI development instructions
  - SPEC.md - System specification
  - 5 sub-agents (infrastructure, function, data-model, test, deploy)
  - 5 slash commands (/init, /build, /test, /deploy, /status)

### Documentation
- ARCHITECTURE.md - Complete system design
- DECISIONS.md - Architectural decision records (20 ADRs)
- ROADMAP.md - 5-phase product roadmap
- CHANGE-LOG.md - This file

### Infrastructure
- Bicep templates for Azure resources (planned)
- GitHub Actions CI/CD pipeline (planned)
- Local development setup scripts

### Data Models
- VendorMaster table schema
- InvoiceTransactions table schema
- Queue message schemas (RawMail, Enriched, Notify)

---

## [0.0.1] - 2024-11-08

### Added
- Initial research documents
  - aips-prd.md - Product requirements document
  - aips-architecture.md - Technical architecture
  - aips-sprint1-setup.md - Sprint planning

- Concept implementation
  - Basic Azure Function structure
  - Placeholder functions (MailIngest, ExtractEnrich, PostToAP, Notify)
  - Shared utilities (models.py, kv.py)
  - Basic requirements.txt

### Planned Features
- Email ingestion from shared mailbox
- Vendor extraction and enrichment
- AP email routing
- Teams notifications
- Transaction logging

---

## Versioning Strategy

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR**: Incompatible API changes or major feature additions
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

### Pre-release Versions
- Alpha: 0.0.x - Initial development
- Beta: 0.x.0 - Feature complete, testing
- RC: 1.0.0-rc.x - Release candidates

---

## Release Types

### Production Releases
- Tagged in git with version number
- Deployed to production environment
- Full testing suite passed
- Documentation updated

### Preview Releases
- Deployed to staging only
- For stakeholder feedback
- May contain experimental features

### Hotfix Releases
- Critical bug fixes only
- Expedited testing and deployment
- Increment patch version

---

## Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

### Types:
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation change
- **style**: Code style change (formatting, etc)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding missing tests
- **chore**: Changes to build process or auxiliary tools

### Examples:
```
feat(mailingest): add Graph API email polling
fix(enrichment): handle missing vendor gracefully
docs(readme): update deployment instructions
perf(storage): implement connection pooling
```

---

## Definition of Done

A feature is considered complete when:

- [ ] Code is written and follows standards
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Deployed to staging
- [ ] Smoke tests passing
- [ ] Stakeholder acceptance received

---

## Breaking Changes Policy

### What Constitutes a Breaking Change:
- Removing or renaming a function
- Changing queue message schema
- Modifying table structure
- Altering API contracts
- Changing configuration requirements

### How to Handle:
1. Document in BREAKING_CHANGES.md
2. Provide migration guide
3. Deprecation notice (1 sprint minimum)
4. Major version increment
5. Stakeholder communication

---

## Archive of Significant Changes

### 2024-11-09: Simplified Scope
- **What**: Removed interactive Teams cards and approval workflows
- **Why**: NetSuite handles approvals, reducing complexity by 50%
- **Impact**: Faster delivery, simpler maintenance

### 2024-11-08: Technology Stack Finalized
- **What**: Chose Azure Functions, Table Storage, Python 3.11
- **Why**: Cost-effective, team expertise, fast delivery
- **Impact**: Significant cost savings vs alternative solutions

### 2024-11-07: Project Approval
- **What**: Invoice automation project greenlit
- **Why**: Manual processing inefficiency
- **Impact**: Significant time and cost savings

---

## Future Milestones

### Version 1.0.0 (MVP Release)
- Core MVP complete
- 80% automation achieved
- Production deployment
- Documentation complete

### Version 2.0.0 (Intelligence Release)
- PDF extraction
- AI vendor matching
- 90% automation

### Version 3.0.0 (Integration Release)
- NetSuite integration
- Multi-mailbox support
- Analytics dashboard

---

**Maintained By:** Development Team
**Update Frequency:** Every significant change
**Review Schedule:** Weekly during active development