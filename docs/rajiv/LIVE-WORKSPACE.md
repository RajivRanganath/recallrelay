# Live workspace: real model calls and PayPal sandbox in the one app

The unified workspace has opt-in live modes. The default launch is unchanged: mock extraction, template briefs, fake payments, no credentials. Live modes use the provider adapters each lane already had; this change connects them to the single-URL workspace and makes the screen report the modes actually running. **PayPal sandbox only. No live-money mode exists.** Labels, campaign and case remain synthetic.

## What each flag turns on

| Flag | Effect | Shown on screen |
|---|---|---|
| `--extractor omniroute --omniroute-env PATH --model MODEL` | **Read label with AI** sends the uploaded photo to a model through the local OmniRoute gateway (`127.0.0.1:20128`). The reply is a suggestion only. | Served model, self-reported confidence per field, uncertain fields left blank with one clarification |
| `--brief omniroute` or `--brief gemini --gemini-env PATH --gemini-model MODEL` | **Draft AI brief** asks a model for the merchant brief. Code checks every number, identifier and citation against the case records; a draft that fails is replaced by the template. | AI-written or template, the served model, and the rejection reason when a draft was not shown |
| `--paypal sandbox --paypal-env PATH --sandbox-case FILE` | Approval calls the PayPal **sandbox**: payment state, refunded balance and dispute checks, an idempotent refund, then a read-back before the case says refunded. | "PayPal sandbox", the operation ID and PayPal's refund ID |
| `--lose-first-refund-response` | Recovery demonstration. The first refund is really sent and accepted, then its acknowledgement is deliberately discarded. | A fault-injection notice, **Refund pending**, then recovery with the same operation ID |

Env files are named by path and parsed for the listed variables only; they are never executed, copied or printed. Keep them outside the repository.

## Run it

1. Start the OmniRoute gateway (`omniroute serve`) if AI modes are used.
2. Create one sandbox payment. A sandbox buyer approves it in the browser; the script never sees a password:

   ```sh
   evidence/.venv/bin/python -B -m resolution.sandbox.make_capture --paypal-env PATH/paypal.env --output PATH/sandbox-case-1.json
   ```

   One capture supports one full 40.00 USD refund. Make a new capture, with a new output file, for each take.
3. Start the workspace:

   ```sh
   evidence/.venv/bin/python -B -m evidence.integrated --port 8101 \
     --extractor omniroute --brief omniroute --omniroute-env PATH/omniroute.env --model gemini/gemini-3.1-flash-lite \
     --paypal sandbox --paypal-env PATH/paypal.env --sandbox-case PATH/sandbox-case-1.json \
     --lose-first-refund-response
   ```

4. Open the printed URL. The header chip must read **Live AI label reading · AI brief · PayPal sandbox refunds**. If it does not, the corresponding flag was not applied; do not describe the run as live.
5. Upload a synthetic label from `evidence/evals/fixtures/` and choose **Read label with AI**. `clear-png.png` shows both identifiers; `cropped.png`, `blurred.png` and `conflicting-batches.png` are uncertainty cases; `instruction-note.png` carries a printed instruction and an excluded batch. Model output can vary between runs, so describe what the screen shows.
6. Confirm identifiers, check the campaign, send for merchant review, draft the brief, confirm remedy conditions, type the exact amount and approve.
7. With `--lose-first-refund-response` the status view shows **Refund pending**. Choose **Check pending refund again**. The same operation ID is re-sent as `PayPal-Request-Id`; PayPal returns the existing refund, and the case becomes **Refunded** after read-back.
8. Optional independent check, read-only: `evidence/.venv/bin/python -B -m resolution.sandbox.verify_refund REFUND_ID --paypal-env PATH/paypal.env`.

Each mode is independent. `--lose-first-refund-response` also works with fake payments, with no account at all, which is the quickest way to see the recovery path.

## Boundaries that did not change

- AI proposes identifiers and prose. Deterministic rules decide the campaign match; a person confirms identifiers, confirms remedy conditions and types the exact amount. No model output approves or sends a refund.
- The merchant service still runs in its own process with its own store. The workspace gateway forwards only the same allowlisted routes; it gained one read-only `GET /api/session` that reports the fault-injection setting.
- The sandbox order is held by the launcher. A browser still supplies only a label. Fixture capture IDs cannot reach PayPal, and a real capture cannot be combined with fake payments.
- The lost acknowledgement is a labelled fault injection wrapped around the adapter at launch. Signature, settlement and refund code are unchanged.
- Loopback only. No webhook route, public host or tunnel is involved.

## Verification: 12 November 2026

Measured on macOS, Python 3.11.16, branch `work/rajiv-live-workspace`:

- 173 evidence tests passed against the actual merchant source with ResourceWarnings as errors, including five new live-workspace tests. 169 merchant tests and three shared contract tests passed unchanged. 19 Node UI tests passed, including three new mode and recovery checks.
- The new sandbox test runs both real services and the gateway against a **local stub of PayPal's API**: approval checks, one accepted refund whose acknowledgement is discarded, `pending` with no refund ID, a repeated approval that sends nothing, then reconciliation. It asserts two refund requests carrying one operation ID, exactly one refund at the provider, and matching customer status.
- A browser walkthrough in Chromium used **fake payments** with `--lose-first-refund-response`: clear example, confirmed assessment, handoff, template brief, remedy confirmation, exact 40.00 approval, **Refund pending** with the fault notice, one explicit re-check, **Refunded** with the same operation ID and matching customer status.

### Real model run through the unified workspace

One browser session on 12 November 2026, uncommitted working tree on `56557d9`, launched with `--extractor omniroute --brief omniroute --model gemini/gemini-3.1-flash-lite --lose-first-refund-response` and **fake payments**. The header read "Live AI label reading · AI brief · fake payments". Every response reported served model `gemini-3.1-flash-lite`, prompt `label-image-2`. One request per image, no retries, no failures.

| Fixture image | Model suggestion shown | After confirmation and rules |
|---|---|---|
| `cropped.png` | model LAMP-100; batch uncertain, left blank; one clarification asked | A detail needs attention |
| `blurred.png` | model and batch both uncertain, left blank | A detail needs attention |
| `conflicting-batches.png` | model LAMP-100; batch uncertain, left blank | A detail needs attention |
| `instruction-note.png` | model LAMP-100, batch B103 | Outside this campaign |
| `clear-png.png` | model LAMP-100, batch B101 | Identifiers match |

The clear case was then sent for merchant review. **Draft AI brief** returned a model-written brief that passed the checker and cited assessment, confirmed-label, order and review. A typed 39.99 was refused; 40.00 was approved; the discarded acknowledgement left the case **Refund pending**; one explicit re-check ended at **Refunded** with the same operation ID and matching customer status. Before the browser session, one direct request for `clear-png.png` returned the same identifiers in 2.74 seconds.

The local gateway accepted loopback requests without a provider key in the env file on this machine; the key stays inside the gateway's own configuration. These are six model calls on development fixtures the prompt was tuned against. They show the workspace wiring works; they are not an accuracy result.

**Not yet measured:** this unified launcher has not been run against the real PayPal sandbox. The sandbox adapter it starts was exercised against real PayPal earlier ([merchant runbook](../vismaya/RUNBOOK.md), [webhook record](../WEBHOOK-RESULTS.md)). Record the first real unified sandbox run here with its date, capture, operation and refund IDs before describing the workspace as verified against PayPal. Native Windows execution of the new tests is left to CI.

These checks cover one synthetic case. They establish no AI accuracy, time saving, exactly-once guarantee or production readiness.
