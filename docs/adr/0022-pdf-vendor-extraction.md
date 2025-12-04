# ADR-0022: PDF Vendor Extraction with Azure OpenAI

**Date:** 2024-11-24
**Status:** Accepted
**Supersedes:** [ADR-0004](0004-email-based-vendor-extraction.md)

## Context

Email-only vendor extraction (ADR-0004) achieved ~80% success rate, leaving 20% of invoices with "unknown" vendor status requiring manual intervention. PDF invoices contain explicit vendor names that could improve accuracy.

## Decision

Use pdfplumber for text extraction combined with Azure OpenAI (gpt-4o-mini) for intelligent vendor name identification from PDF content.

## Rationale

- 95%+ accuracy vs 80% with email-only
- ~$0.001 per invoice cost (affordable at scale)
- ~500ms additional latency (acceptable)
- Graceful degradation to email domain if extraction fails
- No breaking changes to existing flow

## Implementation

- `shared/pdf_extractor.py` - PDF text extraction + OpenAI analysis
- `MailWebhookProcessor/` - Calls PDF extraction before queuing
- Dependencies: `pdfplumber`, `openai`
- Environment: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`

## Cost Analysis

- ~$0.001 per invoice (~$1.50/month at 50 invoices/day)
- Latency: +500ms per invoice
- Accuracy: 95%+ vendor extraction rate

## Consequences

- ✅ 95%+ vendor extraction rate (vs 80%)
- ✅ Reduces manual intervention significantly
- ✅ Graceful fallback to email domain
- ⚠️ Dependency on Azure OpenAI availability
- ⚠️ Additional cost (~$1.50/month)
- ⚠️ Slightly increased latency

## Related

- **Supersedes:** [ADR-0004: Email-Based Vendor Extraction](0004-email-based-vendor-extraction.md)
- See `shared/pdf_extractor.py` for implementation
- See `tests/unit/test_pdf_extractor.py` for tests
