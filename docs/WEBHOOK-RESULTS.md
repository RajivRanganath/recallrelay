# Real sandbox webhook verification: 12 November 2026

## Scope and source

One synthetic case was exercised against the real PayPal sandbox API on merged source `640a7062a9a20a2e26503944a47f838c9ce44326` (PRs #35 and #36). Extraction used mock/manual identifiers; briefs used templates. No live money, real customer data, paid AI call, new payment, recording or submission was involved.

The owner approved a temporary tunnel of at most 30 minutes, the exact callback, one refund of the capture's remaining simulated 20.00 USD and subsequent cleanup. The callback is recorded only in the [approval comment on issue #37](https://github.com/RajivRanganath/recallrelay/issues/37#issuecomment-6815189996). No credential, signature, full webhook body or temporary hostname is committed here. Cloudflare Quick Tunnel and PayPal Sandbox were used without a paid service purchase.

## Method

The reviewed merchant receiver admitted only `POST /v1/paypal/webhook` for the approved public host, with a 10-second intake budget, 32-connection limit and four public handlers. Other public routes remained blocked. Customer and merchant services used separate disposable stores and HTTP handoff.

A temporary test adapter guarded the approved capture, amount and currency and reserved a single outbound refund attempt. It called the real sandbox adapter once, then deliberately discarded the accepted refund acknowledgement by raising `RefundUnknown`. Core signature verification and settlement code were unchanged. This created a pending operation for genuine webhook recovery without a manual reconciliation call or a second approval. Selected metadata was retained outside git; temporary launchers and databases were removed after verification.

## Identifiers and observations

| Item | Observed value |
|---|---|
| Case | `case-demo-1` |
| Assessment | `assessment-6a4317c08bf948b1b8fd3e93c12008da` |
| Sandbox capture | `6WJ74541HH375824T` |
| Approved refund | 2000 minor units, USD (20.00) |
| Operation | `op-60425e3513ae99ac5931c6b5` |
| Sandbox refund | `59U35216XD4211149` |
| Event | `WH-11H9863998696405D-8TS6607284630674B` |
| Event type | `PAYMENT.CAPTURE.REFUNDED` |
| Outbound refund attempts | 1 |
| Genuine verified deliveries | 2 (initial delivery and requested replay) |
| Manual reconciliation calls | 0 |

The capture was already partially refunded: paid 40.00 USD, refunded 20.00 USD, remaining 20.00 USD. Fresh provider checks accepted the remaining amount. Only that remaining simulated balance was refunded; this was not a new 40.00 USD payment.

| UTC on 12 November 2026 | Observation |
|---|---|
| 05:10:02.189314 | Single sandbox refund attempt began. |
| 05:10:04.732921 | Accepted refund acknowledgement deliberately discarded; approval returned `pending`. |
| 05:10:21.158034 | Genuine delivery passed PayPal signature verification. |
| 05:10:22.366413 | Provider read-back returned the matching refund, `COMPLETED`, 20.00 USD and operation `custom_id`. |
| 05:10:22.368807 | Webhook returned HTTP 200, `accepted: true`, `settled: true`. |
| 05:12:22.880904 | PayPal-requested replay passed verification. |
| 05:12:22.882273 | Replay returned HTTP 200, `accepted: true`, `settled: false`; case, operation and refund stayed unchanged. |

Merchant and customer status both reported `refunded` for the same case and operation. Final capture read-back showed paid 4000, refunded 4000 and remaining 0 minor units, USD, status `REFUNDED`.

## Public boundary checks

| Request | Expected and observed HTTP status |
|---|---|
| GET `/` | 403 |
| GET `/health` | 403 |
| GET `/v1/cases` | 403 |
| GET `/v1/paypal/webhook` | 403 |
| POST webhook with forged event and no valid signature | 401 |
| POST webhook with foreign Origin | 403 |

These six checks cover the listed requests, not every possible public request or a general security audit.

## Correction during the exercise

The first disposable customer launcher ran from standard input. Its multiprocessing status worker could not import that entry point, so the first customer status check returned 503. Replacing the temporary launcher with a guarded file entry point fixed that check while preserving the same evidence store, merchant case, operation and refund. No application source change, second refund or manual reconciliation was used. The corrected customer status check passed.

## Cleanup

Cleanup was confirmed by 05:15:15 UTC, within the approved window:

- Temporary webhook deletion returned 204; subsequent lookup returned 404; the sandbox app listed zero webhook registrations.
- The tunnel process stopped. The old public URL returned Cloudflare HTTP 530, with the local origin unavailable.
- Both temporary test services stopped; their disposable databases, launchers and empty tunnel configuration were removed after the report was retained.
- Credentials stayed outside git. The installed tunnel binary is not running as a service.
- The normal loopback customer/merchant launcher was restarted with mock extraction, template briefs and fake payments, without sandbox credentials.

No public access remains. A future external test requires a new scoped approval and suitable sandbox funds; this capture's remaining balance is now zero.

## Supporting verification and limits

Before the external exercise, source `521393a` (included in main) passed 161 evidence tests against the actual merchant source, 169 merchant tests, three shared tests and ten UI tests on macOS. Twelve fixture cases / 60 policy checks had zero failures. Native Windows and Linux evidence CI passed for the final merchant source pin; main's evidence and shared workflows also passed at `640a706`. These are separate from the genuine external delivery evidence above.

One case, one deliberate acknowledgement loss and one replay do not establish general reliability, ordering, exactly-once settlement, production security or user time savings. No new AI accuracy or human evaluation result was measured. Historical documents dated before this run retain their original observations; this record supersedes their claim that real webhook delivery was still unverified. Final demo recording and submission remain separate, unfinished work.
