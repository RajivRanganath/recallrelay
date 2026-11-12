# Hackathon submission pack

Draft prepared 12 November 2026 for the PayPal AI hackathon. **Nothing here has been submitted.** Deadline from the rules summary: 13 November 2026, 01:30 IST (12 November, 12:00 PST). Check each item against the [official rules](https://paypalaihackathon.devpost.com/rules) before submitting; that page could not be fetched automatically while this draft was written.

## Checklist

- [x] Real model run through the unified workspace recorded in [LIVE-WORKSPACE.md](LIVE-WORKSPACE.md)
- [ ] One real PayPal sandbox run through the unified workspace recorded there (date, capture, operation and refund IDs)
- [ ] Video under three minutes, public on YouTube, matching the modes shown on screen
- [ ] Both contributors agree to the license; `LICENSE` merged through a setup PR
- [ ] Repository made public by its owner after a last look at issues and PR comments, which also become public
- [ ] README states what is real, what is sandbox and what is mock
- [ ] Devpost form completed, links opened in a signed-out browser, submission confirmed by both contributors

## Devpost description (draft)

**RecallRelay: recall refunds that admit uncertainty and survive a lost payment response**

### The problem

When a product is recalled, a small merchant has to answer the same question for every customer: is this unit one of the affected ones, and if so, has it been refunded exactly once? The evidence is a photo of a label that may be blurred, cropped or from an excluded batch. The payment step can time out after the refund was already created. Guessing on either side costs money or leaves an unsafe product unresolved.

### Who it is for

A merchant's support or operations person handling one recall campaign, and the customer checking whether their unit is covered. The prototype models one fictional brand, one approved refund campaign and one order.

### What it does

One workspace follows a single case through three steps.

1. **Check label.** The customer uploads a label photo. A model proposes the model and batch identifiers with a self-reported confidence. Anything unreadable, conflicting or below the threshold is left blank and the app asks one targeted question instead of guessing. The customer confirms every identifier. Deterministic campaign rules, not the model, decide match, exclusion or needs-information.
2. **Merchant review.** The same assessment opens for the merchant with the order facts. A model drafts a short brief; code shows it only if every number, identifier and citation appears in the case records, and otherwise shows a deterministic template and says why. The merchant confirms the remedy conditions and types the exact refund amount. A different amount is refused.
3. **Refund status.** The refund goes to the PayPal sandbox. Customer and merchant read the same case, operation and refund.

### How AI is used

- Label reading: image to structured identifiers with explicit uncertainty. Text printed on a label is treated as data, never as instructions.
- Merchant brief: grounded summary with citations, validated by code or replaced.
- AI never decides eligibility, never approves and never moves money. Those stay with deterministic code and a person.

### How PayPal is used

PayPal REST APIs on the **sandbox**: OAuth client credentials, Payments v2 capture refund with `PayPal-Request-Id` idempotency and a `custom_id` binding, capture, order and dispute reads before approval, refund read-back before a case is called refunded, and webhook signature verification for `PAYMENT.CAPTURE.REFUNDED`.

### What is different

Most refund flows are written for the case where everything is read correctly and every response arrives. RecallRelay is built around the two places that go wrong:

- **Uncertain evidence is a first-class result.** An unreadable or conflicting label never becomes eligible. The workspace shows what was uncertain and what was asked.
- **An unknown payment outcome is not a failure and not a success.** The operation ID is stored before PayPal is called. If the response is lost, the case stays pending, nothing is retried automatically, and re-checking sends the same operation ID so PayPal returns the existing refund. The demo deliberately discards a real acknowledgement to show this.
- **Events are hints, not truth.** A verified webhook settles a case only after PayPal's own read-back matches the stored operation, amount, currency and `custom_id`. A replayed event changes nothing.

### What was measured

- One real PayPal sandbox exercise on 12 November 2026: one simulated 20.00 USD refund, acknowledgement deliberately lost, two genuine verified webhook deliveries (original and replay), matching provider read-back and customer status. [Record](../WEBHOOK-RESULTS.md).
- Two real sandbox retry experiments on 9 November 2026: the same request ID returned the same refund both times. [Merchant runbook](../vismaya/RUNBOOK.md).
- Label reading through a real model on twelve synthetic development images: 24 of 24 fields agreed with authored references; one internal participant's median completion time was 4.88 s with AI assistance and 8.03 s typed, with two of twelve cases slower with AI. [Results and limits](EVALUATION-RESULTS.md).
- Merchant brief on fourteen invented cases, including four prompt-injection cases: 12 of 14 model drafts passed the checker in the last run; the other two were replaced by the template.
- Automated checks on 12 November 2026: 173 customer-side, 169 merchant-side, 3 contract and 19 UI tests passed on macOS.

### Limits, stated plainly

Synthetic labels, one fictional campaign and order, temporary storage, no login, loopback only, sandbox funds only. The evaluation used one internal participant and images already seen during development, so it supports no general accuracy or time-saving claim. No merchant has used it. One lost-response exercise and one replay do not establish an exactly-once guarantee. A label photo is not proof of ownership, authenticity or safety.

### How to test it

No account is needed for the default run:

```sh
python3 -m venv evidence/.venv
evidence/.venv/bin/python -m pip install -r evidence/requirements.lock.txt
evidence/.venv/bin/python -B -m evidence.integrated --port 0 --lose-first-refund-response
```

Open the printed URL and follow Check label, Merchant review, Refund status. This run uses mock label reading, template briefs and fake payments, and still shows the lost-response recovery. Real model calls and PayPal sandbox refunds use the flags in [LIVE-WORKSPACE.md](LIVE-WORKSPACE.md) with your own sandbox app and model key.

### Built with

Python 3.11 standard-library HTTP services, SQLite, plain HTML, CSS and JavaScript, JSON Schema contracts, PayPal REST APIs (sandbox), Gemini models reached directly or through a local OmniRoute gateway.

## Video script: target 2:50, hard limit 3:00

Record the live launch from [LIVE-WORKSPACE.md](LIVE-WORKSPACE.md) with `--lose-first-refund-response`. Say only what the header chip shows. Model output can differ between runs: rehearse each image once, and narrate what the screen actually shows rather than this table. Keep terminals with env paths, the PayPal dashboard and any key off screen. Times are targets, not measurements.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Title, then the workspace with the mode chip | A recall means answering one question per customer: is this unit affected, and was it refunded exactly once. RecallRelay handles the two places that go wrong: unclear evidence and lost payment responses. |
| 0:15–0:40 | Upload `cropped.png` (batch cut off), **Read label with AI**, the blank field and the clarification; check the campaign | A model reads the label. Here the batch cannot be read, so it is left blank and the app asks one question. It does not guess, and this case cannot become eligible. |
| 0:40–0:55 | Upload `instruction-note.png`, **Read label with AI**, check the campaign | This label carries a printed instruction. Label text is treated as data: the model has no tools and no authority, and the rules still place this batch outside the campaign. |
| 0:55–1:15 | Upload `clear-png.png`, **Read label with AI**, confirm, check, **Send for merchant review** | A clear label gives both identifiers with the served model and confidence shown. I confirm them. Rules, not the model, find the campaign match. |
| 1:15–1:40 | Merchant review, **Draft AI brief**, the validation note, confirm remedy conditions | The same case opens for the merchant. The brief is model-written, and it is shown only because code found every number and identifier in the case records. |
| 1:40–1:55 | Type 39.99, error; type 40.00 and approve | Approval is bound to this assessment and the exact amount. A different amount is refused. |
| 1:55–2:25 | **Refund pending** with the fault notice; **Check pending refund again**; **Refunded** with operation and refund IDs | This is the PayPal sandbox. For this demo the accepted refund's acknowledgement is deliberately thrown away. The case stays pending. Re-checking sends the same operation ID, PayPal returns the one existing refund, and it is read back before we say refunded. |
| 2:25–2:40 | Customer status line; then the webhook table in `docs/WEBHOOK-RESULTS.md` | The customer sees the same case and refund. Separately, a real sandbox webhook settled a lost response, and its replay changed nothing. |
| 2:40–2:50 | Limits section of the README | Synthetic labels, one campaign, sandbox funds, one internal tester. The measurements and their limits are in the repository. |

Retake a failed sequence or keep the failure honestly; do not present an edited take as uninterrupted. After recording, note the commit, modes, duration and retakes in [LIVE-WORKSPACE.md](LIVE-WORKSPACE.md).
