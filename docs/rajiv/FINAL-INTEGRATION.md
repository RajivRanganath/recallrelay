# Local integrated prototype

Checkpoint: 11 November 2026. Based on merged main `f29a9f3ee0dd46c9fd86b86588f4d30ae3eb94d1` (including resolution PR #28). Changes are on `work/rajiv-final-integration`, within evidence code/tests/UI, Rajiv documentation and evidence CI. They require the other contributor's review before merging.

## Start both apps

Use the existing evidence environment or install `evidence/requirements.lock.txt` into a lane virtual environment first. No root runtime dependencies or provider credentials are needed.

```sh
evidence/.venv/bin/python -B -m evidence.integrated
```

- Customer: <http://127.0.0.1:8101>
- Merchant: <http://127.0.0.1:8102>
- If either port is occupied, choose `--port 8111 --merchant-port 8112`, or use `0` for automatically selected ports and read the printed URLs.
- Ctrl+C stops both owned services and removes their temporary rehearsal data. Restart to get an empty merchant case list. This launcher deliberately uses temporary state; it is not durable hosting.

The launcher starts the actual merchant server as a separate process with a minimal environment, **fake PayPal and template briefs**. It starts the actual evidence server with **mock fixture extraction and deterministic assessment**. Each service owns a separate temporary SQLite database. Neither service imports the other's implementation or opens its database. No provider keys, real AI calls, sandbox refunds or external payment calls are involved in this launcher.

## Same-case walkthrough

1. In the customer app, use **Clear label** or type `LAMP-100` / `B101`.
2. Check the confirmation box and click **Check campaign match**. Note the saved assessment ID. No merchant case exists yet.
3. Click **Send for merchant review**. The backend sends its saved order and that exact saved assessment to the existing `/v1/resolutions` API. The browser supplies only an assessment ID. Remedy conditions are always sent as false.
4. Open **Open merchant review**, then select **case-demo-1** in the merchant list. Do not use **Load demo case** as the handoff: that button is the merchant's separate fixture seeder.
5. The case initially requires manual handling. Review the identifiers and order, then use the merchant's remedy confirmation for this synthetic rehearsal.
6. Request a brief if desired; the launcher shows an explicitly labeled template. Type the exact refund amount `40` and an explicitly synthetic approver name. A different amount is rejected. Approve the **fake** refund.
7. Return to the customer app and click **Read demo case status**. It now shows the merchant's result for the same case. No status GET creates a case or starts a refund.

For missing information, leave the batch blank; both apps retain `needs_information` and propose zero. For exclusion, use `B103`; both apps retain `excluded`. Correct the label, confirm it again, assess and submit a new snapshot before any payment operation. Once the merchant has started or finished a payment operation, changed assessments cannot replace that merchant case. Restart this temporary rehearsal for a fresh independent scenario.

## Handoff and retry behavior

The route is opt-in and available only in the integrated launcher. Ordinary `evidence.demo` and the standalone evidence server retain their existing read-only merchant behavior. Host/origin, JSON framing, body size and receive deadlines still apply. The handoff client permits only explicit loopback HTTP, never follows redirects, validates frozen v1 schemas and returned case IDs, bounds the whole HTTP operation, and never retries automatically or calls approval/reconciliation routes.

Editing an identifier invalidates the UI's saved handoff. The backend rejects an assessment that is no longer the latest saved assessment. A confirmed handoff is recorded in the evidence store; repeating that same transfer reads merchant status rather than reposting and resetting remedy confirmation. Concurrent browser handoffs are rejected while one is running. A merchant refusal or outage is visible, while evidence remains saved and typed entry stays available.

A response loss or crash between merchant acceptance and local acknowledgement can leave an uncertain handoff. Read merchant status and inspect the merchant assessment before retrying. This is not an exactly-once cross-service transaction or an atomic freshness guarantee against concurrent reassessment. A case ID identifies a merchant case, not every later customer edit; the customer status text states that it belongs to the last submitted snapshot.

## Verification scope

Local verification uses Python 3.11.16, installed pinned dependencies, temporary stores and loopback HTTP. Existing real-service integration, the new full-flow tests and the merchant suite use fake or disabled payments; no credentials are needed. Browser rehearsal checked the actual customer → saved assessment → merchant review → wrong-amount rejection → fake approval/refund → customer status path.

The final verification record is [FINAL-INTEGRATION-CHECKS.md](FINAL-INTEGRATION-CHECKS.md). The evidence CI resolution pin is updated to the merged main revision above. Historical evaluation plans, human results and provider reports are preserved; this integration work does not create new accuracy or user-time measurements.

## Remaining acceptance

- Other contributor reviews the integration branch before merge. Hosted CI applies only after publication.
- Record and jointly accept the final demo; issues #5 and #10 include recording, so integration code alone does not finish those whole issues.
- The merchant owner reconciles acceptance/closure of #6–#9 with the implementations already merged. Open tracker state alone does not mean those features are absent.
- Real PayPal webhook delivery is still unverified. The local loopback-only merchant app cannot receive public PayPal deliveries. Existing sandbox reports are separate from this mock integrated rehearsal.
- Root README and shared task-board cleanup require a separate shared/setup PR reviewed by the other contributor, under `AGENTS.md`.

This is a working local synthetic prototype, with explicit human confirmation and fake payments. It is not a deployed service or a production-readiness claim.
