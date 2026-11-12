# Customer handoff dependency and duplicate-review handling

The integrated customer app uses the merchant's existing `GET /v1/cases/{case_id}` endpoint to recover a lost handoff acknowledgement. This endpoint was introduced for the merchant UI and is **not part of the frozen v1 schemas**. Keep its current response compatible until both services coordinate a replacement. A future formal contract belongs in a dedicated shared contract PR; this note does not silently freeze or rename shared fields.

The evidence client relies on:

- `resolution`: the schema-valid v1 resolution response for the requested case.
- `assessment`: `assessment_id`, `decision`, `model`, `batch`, `reason`, `evidence`, `mode`, `missing_fields` and `clarification`.
- `binding`: matching `assessment_id`, `campaign_version`, `capture_id` and `currency`.
- `order`: `order_id`, `paid_minor`, `previously_refunded_minor`, `age_days` and `quantity`.

The client compares these values to its own saved assessment and order before acknowledging an already accepted handoff. A plain `GET /v1/resolutions/{case_id}` response lacks structured assessment identity and cannot establish the same binding. Do not remove/reshape these fields without coordinating the evidence client and both services' integration checks. All reads remain one-way HTTP; neither service accesses the other's database.

## Merchant-side protection

Inside the existing SQLite write transaction, `CaseStore.save_review` compares the incoming schema version, complete order and complete assessment with the saved snapshot. When those match and merchant remedy confirmation is already true, a delayed handoff carrying false returns the stored response and leaves the stored request untouched. It also preserves a later provider hold; a duplicate handoff cannot reopen approval or replace that hold's explanation.

A genuinely changed assessment or order does not inherit prior remedy confirmation. A merchant's explicit true-confirmation/review action retains its existing behavior, including re-reviewing a provider hold after the condition is resolved. Pending, refunded and failed states retain their existing review lock and cannot be overwritten by this path. No new refund or provider call occurs during review.

This closes the confirmation reset for identical handoffs, including concurrent confirmation and replay transactions. It does not impose an ordering policy between different assessment snapshots, create a distributed transaction, verify a human's identity, or establish exactly-once delivery.

Tests: `resolution/tests/test_review_replay.py` and the repeated-handoff HTTP regression in `test_server.py`. They use synthetic records, temporary databases and no provider credentials.

## Assessment response identity

`EvidenceClient.assess` accepts a response only when its case ID, campaign ID and campaign version match the requested order/campaign snapshot. A valid schema and matching case alone are insufficient: an older, newer or different campaign is a visible `EvidenceUnavailable` error and is not passed on as an assessment. `test_evidence_client.py` checks these mismatches against synthetic HTTP responses. The HTTP caller must continue to stop the workflow on this error; it must not substitute an eligible fixture or silently downgrade the campaign.
