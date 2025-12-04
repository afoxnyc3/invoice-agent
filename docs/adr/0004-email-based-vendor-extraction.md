# ADR-0004: Email-Based Vendor Extraction

**Date:** 2024-11-09
**Status:** Superseded by [ADR-0022](0022-pdf-vendor-extraction.md)

## Context

Need to identify vendor from invoice for MVP. Full PDF parsing was estimated at 6 weeks vs 2 weeks for email-only approach.

## Decision

Extract vendor from email sender/subject for MVP, with plan to add AI extraction in Phase 2.

## Rationale

- 80% of vendors identifiable from email alone
- Avoids complex PDF parsing
- Faster implementation (2 weeks vs 6 weeks)
- Can add AI extraction in Phase 2

## Consequences

- ✅ Quick MVP delivery
- ✅ Simple, reliable logic
- ⚠️ 20% unknown vendor rate initially
- ⚠️ Manual intervention required for unknowns

## Related

- **Superseded by:** [ADR-0022: PDF Vendor Extraction](0022-pdf-vendor-extraction.md)
- See `shared/email_processor.py` for domain extraction logic
