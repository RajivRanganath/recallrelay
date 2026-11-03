# Frozen v1 boundary

Read the two OpenAPI JSON files, schemas and fixtures. Amounts are integer minor units, USD only for MVP. IDs are strings. Fixture capture IDs are deliberately fake and must never reach PayPal. `mode: mock` means no real assessment or financial action occurred.

## Ownership and call direction
Evidence (Rajiv) exposes POST /v1/assessments and GET /v1/assessments/{case_id}. Resolution (Vismaya) owns canonical cases and calls evidence with its approved campaign and order snapshot. Evidence owns evidence storage and computed assessments.
Resolution exposes POST /v1/resolutions (review only, no money) and GET /v1/resolutions/{case_id} (latest state). Evidence's customer backend reads resolution status. Do not create synchronous cycles: neither GET calls back to the other service.

An eligible assessment means the identifiers match this campaign only. It does not authorize payment. `remedy_conditions_met` is merchant-controlled; never trust a browser-provided true value. Resolution checks eligibility, campaign/assessment version, merchant authority, conditions, amount, age, outstanding dispute and remaining balance before approval/execution. Final payment routes are internal to resolution and intentionally outside this shared contract.

`label.image_base64` and `mime_type` may be null for a typed-entry baseline. Real image ingestion needs size/type checks and private storage. Confirmed identifiers mean customer-confirmed text, not authenticated product ownership. If identifiers are uncertain, evidence returns needs_information with missing_fields and a targeted clarification. Missing data must not be silently inferred.

Mode `ai` identifies actual provider-assisted processing, not correctness. `manual` is confirmed typed input plus deterministic checks. `sandbox` refers only to actual PayPal sandbox operations. An evidence decision does not imply a refund is completed.

## Stable integration
No shared database or imports. Each backend uses an HTTP client and an env-configured base URL (EVIDENCE_BASE_URL / RESOLUTION_BASE_URL). Timeout, malformed payload and 503 must become visible errors, not fabricated successful responses. A read-only GET must never refund. Don't log images or secrets.

Contracts remain v1 until a dedicated change PR is approved by both contributors. Add an adjacent v2 rather than breaking the working mocks. Both lane CI jobs run on any contract change.

## Mock limitations
Mocks accept fixture-shaped JSON and echo identifiers. They select canned scenarios via X-Mock-Scenario; they do not run eligibility rules, AI, auth or payments. GET only recognizes case-demo-1. Use mock fixtures for development, never as measured model performance. Unknown route/scenario is rejected. Full JSON Schema validation lives in CI/tests; mock runtime performs basic required-field validation only.
