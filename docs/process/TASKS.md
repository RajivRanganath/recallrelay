# Balanced task board

## Delivery status: 12 November 2026

Issues #1–#4 and #6–#9 are closed. Both implemented services and the explicit same-case customer/merchant HTTP flow are merged, including merchant hardening, full Windows evidence coverage and the final unfinished-request correction through [PR #36](https://github.com/RajivRanganath/recallrelay/pull/36). [PR #35](https://github.com/RajivRanganath/recallrelay/pull/35) supplies the handover record, current merchant CI pin and combined recording outline. The owner explicitly authorized the merchant ownership exception and the contributor-review merge exception for #35 and #36. This is a local synthetic prototype, not production acceptance. [#5](https://github.com/RajivRanganath/recallrelay/issues/5) and [#10](https://github.com/RajivRanganath/recallrelay/issues/10) remain open because recording is deliberately deferred; clean-start instructions and technical integration are delivered.

Real sandbox webhook delivery and replay were verified under a specific temporary exception on 12 November, tracked in [#37](https://github.com/RajivRanganath/recallrelay/issues/37). [Measured results](../WEBHOOK-RESULTS.md) record one simulated 20.00 USD refund, two genuine verified deliveries, operation-bound provider read-back, matching customer status, negative checks and completed cleanup. No public listener or webhook registration remains. Future public access still requires approval under [the verification boundary](../WEBHOOK-VERIFICATION.md). No final video or submission is claimed. The original effort allocation and scope below remain the planning record.

[PR #39](https://github.com/RajivRanganath/recallrelay/pull/39) adds the single-URL workspace for both roles: label assessment → automatically loaded merchant review → matching customer/merchant refund status. It preserves explicit remedy confirmation and exact-amount approval, separate service stores and frozen v1 payloads. [PR #40](https://github.com/RajivRanganath/recallrelay/pull/40) is the dedicated shared startup/status documentation follow-up. See [the unified guide and measured checks](../rajiv/UNIFIED-WORKSPACE.md); PR review/merge state remains visible on GitHub. These changes add no recording, provider call or public deployment.

Points express relative effort, not time. Each person has 20 points across the same categories. Re-estimate after the first working slice; reduce scope if needed rather than moving all backend work to one person.

| Task | Rajiv: evidence lane | Vismaya: resolution lane | Points each |
|---|---|---|---|
| 1 AI | Structured label extraction; confidence/uncertainty; one targeted clarification; prompt-injection tests | Case summary with record citations; missing-remedy questions; unsupported-claim and injection tests | 5 |
| 2 Backend | Evidence persistence, image limits, assessment endpoint, confirmed identifier rule checks | Case persistence, brief endpoint, human approval, PayPal sandbox adapter and status reconciliation | 6 |
| 3 UI | Customer upload, extracted-field confirmation, clarification, result/status views | Merchant case list, evidence/brief review, exact-amount approval, refund result views | 4 |
| 4 Evaluation | Labeled image variants + typed-entry baseline; extraction and clarification results | Labeled case briefs + deterministic template baseline; payment retry/concurrency/failure tests | 3 |
| 5 Integration/demo | HTTP client for resolution status; customer-side integration smoke; first demo half; own runbook | HTTP client for evidence assessment; payment-side integration smoke; second demo half; own runbook | 2 |
| Total | AI + backend + UI + tests + handoff | AI + backend + UI + tests + handoff | 20 |

## Why these can run independently
- Each lane has a fixture request and response, a JSON Schema, an OpenAPI file and a runnable opposite-service mock.
- Neither lane requires the other lane's database, credentials, model provider, frontend framework or package lock.
- Both lane UIs are separate routes/apps; no shared UI component file. Keep the first integration as links between customer and merchant views with a case ID.
- Backend APIs are internal server-to-server boundaries. Browsers call their own lane backend; do not share secrets or rely on permissive CORS.
- The resolution lane owns canonical case/payment state. The evidence lane owns evidence/assessment records. Handoff uses a frozen assessment snapshot, not shared mutable state.

## Original delivery sequence (same for both)
1. First slice: lane skeleton + mock client + one UI path. No external keys required.
2. Next: deterministic rules/storage + provider adapter interfaces + failure paths.
3. Next: actual AI/provider setup with account owner consent; benchmark against baseline.
4. Nov 9 target: connect both lanes and freeze features.
5. Nov 10 target: reproduce from clean checkout, record demo, finish docs. Dates are targets, not promises.

## Integration responsibilities
Rajiv writes evidence/tests/test_resolution_client.py against the resolution mock and later actual service. Vismaya writes resolution/tests/test_evidence_client.py against the evidence mock and later actual service. Each fixes their own side. Shared contract edits use a standalone PR; keep v1 working while it is reviewed.

## Definition of done
Both: own lane tests green; schema-conformant output; documented mock/provider mode; no secrets; runnable lane README; known failures reported; cross-lane smoke tested. Evidence: uncertain label never auto-eligible. Resolution: AI never approves payment; repeated operation cannot knowingly create a new refund; provider failures remain visible. Real sandbox success requires actual PayPal IDs and read-back, not a mock screenshot.

## Live GitHub tasks

| Owner | Task | Points |
|---|---|---|
| @RajivRanganath | [#1](https://github.com/RajivRanganath/recallrelay/issues/1) | 5 |
| @RajivRanganath | [#2](https://github.com/RajivRanganath/recallrelay/issues/2) | 6 |
| @RajivRanganath | [#3](https://github.com/RajivRanganath/recallrelay/issues/3) | 4 |
| @RajivRanganath | [#4](https://github.com/RajivRanganath/recallrelay/issues/4) | 3 |
| @RajivRanganath | [#5](https://github.com/RajivRanganath/recallrelay/issues/5) | 2 |
| @VismayaM2005 | [#6](https://github.com/RajivRanganath/recallrelay/issues/6) | 5 |
| @VismayaM2005 | [#7](https://github.com/RajivRanganath/recallrelay/issues/7) | 6 |
| @VismayaM2005 | [#8](https://github.com/RajivRanganath/recallrelay/issues/8) | 4 |
| @VismayaM2005 | [#9](https://github.com/RajivRanganath/recallrelay/issues/9) | 3 |
| @VismayaM2005 | [#10](https://github.com/RajivRanganath/recallrelay/issues/10) | 2 |
