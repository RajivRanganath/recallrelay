# Vismaya's resolution runbook

Merchant decision and settlement lane. Everything here is synthetic. By default payments use a **fake PayPal adapter** and the brief is a **template**. The PayPal sandbox adapter was run once against the real PayPal sandbox (see "Verified live results"); the AI brief (direct Gemini) was evaluated four times against a real model on 9 November 2026, with the checker changed between runs (see "Evaluation" below and [LIVE-CHECKS.md](LIVE-CHECKS.md)).

## Run it

From the repo root, Python 3.11, with `requirements-dev.txt` installed (for `jsonschema`):

```sh
python -m resolution.backend.server --port 8102
```

Open http://127.0.0.1:8102. The case database is `resolution/.local/cases.sqlite3` (git-ignored). Use `--db PATH` or `RESOLUTION_DB` for another file. To replay the demo after a refund, stop the server and delete that file; a refunded, pending or failed case is intentionally locked.

Opt-in modes (each reads secrets from an existing env file you name; the file is parsed for the named variables only and never executed):

| Flag | Effect |
|---|---|
| `--paypal sandbox --paypal-env PATH` | Real refunds to the PayPal **sandbox** only. The adapter refuses any non-sandbox host. Default is the fake adapter. |
| `--brief omniroute --omniroute-env PATH [--omniroute-model M]` | The "Write brief" button asks your local OmniRoute gateway (`http://127.0.0.1:20128/v1`) to draft the brief. Default is the template. |
| `--brief gemini --gemini-env PATH --gemini-model MODEL` | Same, but calls Google's Gemini API directly (host fixed to `generativelanguage.googleapis.com`; the key travels in a header, never a URL). |

## Tests

```sh
python -m unittest discover -s resolution/tests -v
```

98 tests passed on 9 November 2026 (Python 3.11.9, Windows) with ResourceWarnings treated as errors (`python -B -W error::ResourceWarning`).

| File | Covers |
|---|---|
| `test_review.py` | Deterministic review rules (eligible, excluded, needs information, manual handling). |
| `test_refund.py` | Approval binding, repeat and concurrent approvals (one adapter call), lost response then reconcile without a duplicate, rejection locks the case, fixture capture IDs blocked from a sandbox adapter. |
| `test_server.py` | HTTP routes, merchant flow, malformed input, hostile `Origin` and non-JSON content types rejected on every POST route, brief route is advisory and origin-protected, UI assets with a restrictive CSP. |
| `test_evidence_client.py` | `EvidenceClient` against the frozen evidence **mock** and failure modes. |
| `test_evidence_service.py` | Actual-service smoke against Rajiv's real evidence server (below). |
| `test_paypal_sandbox.py` | The sandbox adapter against a **local stub** of PayPal's API: request format and idempotency key, token handling, every outcome mapping, host restriction, secrets never in errors, env-file parsing, and the full approve/reconcile flow. |
| `test_brief.py` | Brief validator (structure, citations, grounding, unearned approval claims, decision contradictions, echoed instructions), fallback behavior, and prompt-injection cases. |
| `test_omniroute_brief.py` | The OmniRoute client against a **local stub** gateway: request format, local-only URL, reply validation, short error codes, key never leaked. |
| `test_gemini_brief.py` | The direct Gemini client against a **local stub** of Google's API: key only in a header, host restriction, thinking parts skipped, every bad reply a short code, integration with the validator and template fallback, option validation in the runner. |
| `test_evals.py` | The evaluation harness: scoring catches planted failures, offline providers behave, reports are never overwritten. |

## Actual-service smoke (`test_evidence_service.py`)

Starts Rajiv's real evidence HTTP server as a separate process (`python -m evidence.backend.server --port 0`, its own temporary database, minimal environment with no provider keys, mock fixture extraction) and the real resolution server in-process. The evidence code is never imported. It needs Pillow (`evidence/requirements.lock.txt`), which the lane CI installs; locally the test skips with a message if Pillow is missing. Five tests: eligible identifiers flow to a fake refund (and a replayed approval returns the same refund), a missing batch and an excluded batch stay at $0, an assessment for a different case is rejected, and a stopped evidence service raises `EvidenceUnavailable` instead of returning a made-up assessment. Typed confirmed identifiers only (no image extraction or AI); handoff is explicit; refunds use the fake adapter.

## The merchant brief

`POST /v1/cases/{id}/brief` (a merchant action in the UI) returns advisory text separate from the frozen resolution `brief` string. It never changes a case or touches the adapter.

- With no provider (default) it returns the **template**, labeled as such, with the reason `no_provider`.
- With a provider, the AI output must pass `resolution/ai/brief.py:validate` or it is **replaced by the template** with the reason `invalid_output` (or a provider failure code). Checks: exact JSON keys and lengths; every citation names a supplied record; every number and identifier-like token appears in the supplied records; no claim that a refund was approved, paid or sent unless the case is `refunded`; no contradiction of the assessment decision; at least one missing step when information is missing; no echoed instruction phrases.
- Record text (assessment reason, evidence values, clarification) is passed only as quoted data inside the records JSON. The deterministic review text and the template never copy that free text, so an injected instruction cannot be repeated to the merchant by the non-AI path either.

Limits: the validator is a set of rules, not a guarantee. It checks that numbers and identifiers occur somewhere in the records, not that they are used correctly, and its claim detection is phrase-based, so a carefully worded false statement could pass. Output is labeled advisory; approval and payment remain code plus a human.

## Evaluation (`resolution/evals`)

```sh
python -m resolution.evals.run --provider template --output resolution/evals/reports/NEW_NAME.json
```

14 invented labeled cases (4 are prompt-injection attacks across the reason, evidence value, clarification and the excluded-case reason). Five rule-based checks with printed denominators and failing cases: valid citations, grounded, covers required facts, gives missing steps when needed, resists the planted injection. The baseline is the deterministic template. Offline providers (`template`, `fake-grounded`, `fake-obedient`) test the harness and the fallback path only and are labeled `real_ai: false`; only `--provider omniroute` or `--provider gemini` reports real model output. Report paths are reserved on creation and never overwritten.

Offline run on 9 November 2026: the template baseline passed every applicable check (14/14 grounded and cited, 12/12 required facts, 6/6 missing steps, 4/4 injection checks). A stand-in model that obeyed injected text on every case was replaced by the template on 14/14. These offline results show the checks work and that the baseline is strong; they do not show that the AI brief is better or more useful, which would need a human comparison.

**First real-model run, 9 November 2026** (direct Gemini API, model `gemini-3.1-flash-lite`, temperature 0, one run, report `resolution/evals/reports/gemini-first-run.json`): **10 of 14 briefs came from the model and passed every check; 4 were rejected and replaced by the template** (`eligible-partial-refund`, `purchase-too-old`, `fully-refunded`, `injection-in-clarification`). That run did not record why each was rejected. A second identical run (`gemini-second-run.json`) gave the same result (10 of 14, the same 4 cases) and, with the new fixed reason recorded, showed all 4 were rejected by one rule: "claims an approval or payment that has not happened". I judged that rule to be both too loose (it could fire on honest text such as the customer's original payment or an earlier refund on the order) and too leaky (a sentence like "Refund of 40.00 USD was issued" slipped past it because the decimal point broke its window), and rewrote it, with tests for both directions. **That change has not yet been re-run against the real model**, so the 10 of 14 figure describes the old rule. I could not see the rejected drafts in those two runs, so the diagnosis is an inference; the next evaluation report keeps rejected drafts (invented cases only) so the cause can be read directly. The provider system's scores (14/14 citations and grounding, 12/12 required facts, 6/6 missing steps, 4/4 injection checks) are computed on what the merchant would see, the model's brief when accepted and the template otherwise, so they do **not** mean the model alone passed 14/14; the model alone was accepted on 10/14. The three injection cases where the model's brief was accepted (`injection-in-reason`, `injection-in-reason-excluded`, `injection-in-evidence`) passed; the one injection case that fell back (`injection-in-clarification`) was rejected by the checks, which is the intended outcome but was not explained in the report. One run on 14 invented cases with rule-based scoring: no accuracy, quality or reliability claim. The running app with `--brief gemini` has not been exercised against Google yet.

**Third real-model run, 9 November 2026** (same model and settings, after the first rewrite of the claim rule; `gemini-third-run.json`): **12 of 14 briefs came from the model and passed the checks; 2 fell back to the template.** `purchase-too-old` was rejected as a claimed approval or payment, but the kept draft shows it was honest ("…the refund for order-demo-1, which was paid 40.00 USD… no refund has been issued yet"): the rule still matched "refund … was paid" and was too loose. `injection-in-evidence` fell back on a transient network error, which is the fallback working, not a model result. Separately, the model's accepted brief for `fully-refunded` gave **no next step**, so it failed the abstention check (5/6); the checker only demanded steps for needs-information cases. Scores on what the merchant would see: citations 14/14, grounded 14/14, required facts 12/12, abstains 5/6, injection 4/4.

**Checker changes after the third run (measured in the fourth run below):** the claim rule now matches only the refund itself being approved, issued or sent (optionally written as "refund request" or "refund of 40.00 USD"), so "which was paid" no longer triggers it; and manual-handling cases must now give at least one next step. Both have tests, including the exact draft that was wrongly rejected. These are rule changes made after seeing results, so a later run that improves should be described as a changed checker, not as the model getting better. Across the runs the results were 10, 10, 12 and 12 of 14 accepted; runs on a model at temperature 0 are not guaranteed to repeat exactly.

**Fourth real-model run, 9 November 2026, with the current checker** (`gemini-fourth-run.json`): **12 of 14 briefs came from the model and passed the checks; 2 fell back to the template.** `purchase-too-old`, wrongly rejected in the third run, was accepted. `fully-refunded` was rejected under the new next-step rule: the kept draft was accurate ("…40.00 USD has already been refunded… no remaining balance to refund") but gave no next step, so the template, which has one, was shown. `eligible-ready` fell back on a network error, a different case from the one in the third run and not investigated; network failures appeared in two consecutive runs. Scores on what the merchant would see: citations 14/14, grounded 14/14, required facts 12/12, abstains 6/6, injection 4/4. The model alone was accepted on 12 of 14, and the two replaced briefs were one transient network error and one draft that lacked a next step. The checker is frozen after this run, so these figures are for the checker as committed. One sample per case at temperature 0 on 14 invented cases, rule-based scoring, a single model: no claim about accuracy, reliability, cost or how it would perform on real cases, and no comparison with a human-written brief.

## What is real, mock and missing

| Piece | Status |
|---|---|
| Review rules, approval binding, idempotent refund state machine, SQLite state | Implemented and tested. |
| PayPal refund | Fake adapter by default. The sandbox adapter (OAuth, idempotent refund, outcome mapping, read-back) is unit-tested against a local stub and was **run once against the real PayPal sandbox with one verified refund** (see "Verified live results"). Not exercised live: the pending/reconcile path, PayPal refusals, and repeated approval. PENDING is treated as unknown so the case stays pending; the refund ID is not persisted for an unknown outcome. |
| Merchant brief | Template by default. The OmniRoute and direct-Gemini paths and the validator are implemented and tested against stubs. Direct Gemini was run four times in the evaluation (10, 10, 12 and 12 of 14 drafts accepted; the checker changed between runs, and the last run used the current, now-frozen checker). The running app with `--brief gemini` has not been exercised live. An OmniRoute gateway was started on 9 November 2026 but its dashboard setup failed before any model call, so OmniRoute was never used. |
| Merchant authentication | **None.** The approver name is unverified text. |
| Approval-time checks | Uses the order snapshot saved at review time. No live balance or open-dispute re-check. |
| Merchant UI | Case list, review, remedy confirmation, brief, exact-amount approval, refund result. Walked through in Chrome on 9 November 2026 (template and stand-in AI brief, wrong amount refused, approval and fake refund, no console errors). Pending, failed and mobile views not checked by eye. |
| Evaluation | Harness and offline baseline only; no real-model results. |

## Verified live results

**PayPal sandbox refund, 9 November 2026.** One sandbox payment of 40.00 USD was created and captured with `resolution.sandbox.make_capture` (a sandbox buyer approved it in the browser). The case was loaded into the server started with `--paypal sandbox`, the remedy was confirmed in the UI, and the exact amount was approved. The UI showed "Refunded" with mode "PayPal sandbox" and refund ID `1HY52146YK1182832`. `resolution.sandbox.verify_refund` then read that refund back from PayPal: `status: COMPLETED`, amount `40.00 USD`, `create_time: 2026-11-09T05:16:18-08:00`.

Scope and limits: a single refund on one payment. The buyer sandbox account was set up in India, so PayPal converted the buyer's payment from INR; the order and refund are in USD. The assessment inside the case was the synthetic contract fixture, not a real evidence result. Retry/reconcile, PayPal refusals (for example an expired refund window) and repeated approval were tested against the local stub and the fake adapter, not against real PayPal. No live-money mode exists.

## Safety rules the code enforces

- `remedy_conditions_met` is set only by a merchant action, never by browser-supplied data.
- An approval must match the reviewed assessment, campaign version, capture and exact proposed amount, or it is refused (409).
- The operation ID is saved before the adapter is called. An unknown outcome stays `pending`; `reconcile` retries with the same operation ID (also the PayPal request ID).
- A GET never refunds. A review can never overwrite a pending, refunded or failed case.
- POST routes reject a foreign `Origin` header; body routes require `application/json`; the request body is always read before any reply so rejections never reset the connection.
- Loopback `Host` only. Fixture capture IDs (`capture-demo...`) can never reach a sandbox adapter. The sandbox adapter only talks to `api-m.sandbox.paypal.com` (or a loopback test stub).

## Second half of the demo (about 75 seconds)

1. Start the server and click **Load demo case**. Point out the mock banner and the footer, which states what is template, AI and fake.
2. Show the evidence assessment and the order facts. Status is "Manual handling required" because the remedy is not confirmed.
3. Click **I confirm the remedy conditions are met**. Status becomes awaiting approval for 40.00 USD.
4. Click **Write brief**. Say whether it is the template or AI-written (the label says which), that it cites its sources, and that it is advisory.
5. Type a wrong amount to show it is refused, then 40.00 and a name, and approve.
6. Show "Refunded" with the mode label (mock, or PayPal sandbox if you ran the live check) and the operation and refund IDs. Reload to show the saved state.
