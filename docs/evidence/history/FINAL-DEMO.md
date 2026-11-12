# Final same-case demo outline

Prepared 12 November 2026. This is a checked local rehearsal and recording script, **not a completed video or a measured 150-second take**. Both halves use the same customer assessment and merchant case. The [previous standalone outline](DEMO.md) remains historical evidence.

## Fresh start

From the repository root, use the existing Python 3.11 lane environment:

```sh
evidence/.venv/bin/python -B -m evidence.integrated --port 0 --merchant-port 0
```

Windows PowerShell:

```powershell
.\evidence\.venv\Scripts\python.exe -B -m evidence.integrated --port 0 --merchant-port 0
```

For installation, follow [FINAL-INTEGRATION.md](FINAL-INTEGRATION.md), then use [the unified workspace](../UNIFIED-WORKSPACE.md). Open the one printed RecallRelay URL. The launcher creates fresh, separate temporary stores behind one application, mock fixture extraction, deterministic assessment, template briefs and **fake payments only**. It reads no PayPal credentials. Ctrl+C stops the workspace and both owned services and removes the rehearsal stores.

Use the workspace's **Send for merchant review** action. It opens the same case automatically. Keep case-demo-1, its saved assessment ID and the visible mode labels readable.

## Recording outline: 150-second target

The targets allocate screen time; they are not observed task timings.

| Target | Action | Suggested narration |
|---|---|---|
| 0–12 s | Show the synthetic notice and mock extraction label. | These are fictional labels and orders. This walkthrough uses mock suggestions, template text and fake payments. |
| 12–27 s | Choose Unreadable batch, use the sample, confirm readable values and check the campaign. | An unreadable batch stays blank. The app asks for the missing identifier instead of guessing. |
| 27–40 s | Choose Excluded batch, use the sample, confirm and check B103. | This batch is excluded from this campaign. That does not mean the product is safe. |
| 40–60 s | Choose Clear label, use the sample, inspect LAMP-100/B101, confirm and check the campaign. | I confirm the identifiers. Deterministic rules find a campaign match; that alone does not authorize a refund. |
| 60–75 s | Send for merchant review; the workspace opens case-demo-1 automatically in Merchant review. | This explicit handoff sends the saved assessment. The merchant reviews the same case and assessment in the same app. |
| 75–95 s | Inspect evidence and order; choose Generate template brief. | The brief cites case records and stays advisory. This run uses a labeled template, not a live AI model. |
| 95–110 s | Confirm remedy conditions for this synthetic fixture; inspect 40.00 USD. | The merchant separately confirms remedy conditions. Approval is bound to this assessment and exact amount. |
| 110–125 s | Enter 39.99 and a fictional reviewer name, then attempt approval. Show the error. | A different typed amount is refused. The name is unverified text; this prototype has no merchant login. |
| 125–140 s | Enter 40.00, approve and show the fake refund result. | This is the fake adapter. No real money moves. Operation and fake refund identifiers remain visible. |
| 140–150 s | The workspace opens Refund status; show the matching customer and merchant outcome for case-demo-1. | Both roles read the same case and operation. Real sandbox webhook delivery was checked separately; this screen uses fake payments. |

Wait for visible results when requests are still running. Retake a failed sequence or preserve the failure honestly; do not describe an edited or interrupted take as uninterrupted. Record actual take duration separately from human evaluation results.

## Checked rehearsal

On 12 November 2026, source `521393a` ran on two ephemeral loopback ports. The browser walkthrough checked clear-label assessment, explicit same-case handoff, template brief, remedy confirmation, 39.99 rejection against 40.00, exact fake approval and the customer's refunded status. Missing/excluded rules are separately covered by fixture replay and service tests. This records no video, spoken duration, live extraction, live brief, sandbox refund or public webhook delivery.

## Provider material and recording handoff

- Existing [evaluation results](../EVALUATION-RESULTS.md) and the [merchant runbook](../../resolution/RUNBOOK.md) record separate provider experiments and their limits. Do not label this default walkthrough live AI or PayPal sandbox.
- The separately approved real sandbox webhook exercise and cleanup are recorded in [the measured result](../../WEBHOOK-RESULTS.md). The public access exception is over; a future exercise needs new scoped approval.
- Preserve the visible modes, same-case linkage, rejection example and final customer status. Keep credentials, dashboard account details and env files off screen.
- Save the final recording with its commit, modes, actual duration and retries. Recording and submission remain unperformed until an actual artifact and destination are supplied. Public release or submission is a separate action.
