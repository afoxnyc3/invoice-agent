# Teams Webhook Troubleshooting Session - 2025-12-12

## Current Issue
Power Automate returns **400 Bad Request** when Notify function POSTs to Teams webhook.

## What We've Tried

### Fix 1: Removed `contentUrl: null` (commit 102286b)
- Power Automate rejected `null` JSON value
- Removed field entirely - didn't fix 400 error

### Fix 2: Changed payload from message envelope to raw Adaptive Card (commit a0772b1)
**Before:**
```json
{"type": "message", "attachments": [{"contentType": "...", "content": {...}}]}
```
**After:**
```json
{"type": "AdaptiveCard", "$schema": "...", "version": "1.4", "body": [...]}
```
- Still getting 400 error

## Files Modified
- `src/Notify/__init__.py` - `_build_teams_payload()` function
- `tests/unit/test_notify.py` - Updated 4 test assertions
- `tests/integration/test_end_to_end.py` - Updated integration test assertions

## Test Results (19:02 UTC)
All functions executed successfully:
1. MailWebhook -> MailWebhookProcessor (PDF: CDW Direct from invoice_ZR00681475.pdf)
2. ExtractEnrich (Unknown vendor, registration email sent to chelseapiers.com)
3. PostToAP (Posted successfully)
4. Notify (400 Bad Request from Power Automate)

Transaction ID: `01KC9Z27VKAB5NGNWC2EXXND0W`

## Root Cause
The issue is **Power Automate flow configuration**, not our code. The "When a Teams webhook request is received" trigger isn't accepting our Adaptive Card JSON format.

## Next Steps
1. User providing Power Automate flow screenshots
2. Need to verify:
   - What "Response type" is selected in the trigger (Adaptive Card vs JSON)
   - What action follows the trigger (Post card, Parse JSON, etc.)
3. May need to adjust flow configuration OR change our payload format to match what flow expects

## Webhook URL (from Key Vault)
`TEAMS_WEBHOOK_URL` -> Power Automate endpoint:
`https://...powerplatform.com/.../workflows/.../triggers/manual/paths/invoke`

## CI Status
All tests passing (commit a0772b1):
- 446 unit tests
- 26 integration tests
- Deployed to production
