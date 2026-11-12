# Real PayPal sandbox webhook delivery: prerequisites

## Current status: 12 November 2026

One explicitly approved sandbox recovery and replay exercise is complete on source `640a7062a9a20a2e26503944a47f838c9ce44326`. See [measured results and cleanup](WEBHOOK-RESULTS.md) and [issue #37](https://github.com/RajivRanganath/recallrelay/issues/37). A genuine verified event settled the pending synthetic case after a deliberately lost refund acknowledgement; a second verified delivery left it unchanged. The temporary registration and public tunnel have been removed. The exception covered this exercise only; it does not authorize future public access, live money or deployment.

The dated preparation below describes the earlier state. Its absent-credential/callback statements are historical. The approval and evidence requirements remain applicable to a future exercise; do not reuse the expired callback or assume the sandbox capture still has refundable funds.

## Historical preparation: 11 November 2026

Status on 11 November 2026: **not performed**. The owner reports no approved public HTTPS callback and no registered webhook ID. Sandbox credentials exist on Vismaya's Windows machine outside the repository; they are not available in the current Mac environment. No public tunnel, dashboard registration, refund or provider call was performed for this preparation.

PayPal delivers webhooks as HTTPS POSTs to a URL registered for the app that produced the event. Receipt and authenticity verification are separate steps; a 2xx response alone does not establish authenticity. The current app uses PayPal's verification API before processing an event. See the [official webhook overview](https://developer.paypal.com/api/rest/webhooks/) and [management/signature API](https://developer.paypal.com/api/webhooks/v1).

## What must be agreed before an external test

The project rules prohibit public deployment. This document is preparation, not an exception or authorization. Before any public setup, record approval identifying:

- The sandbox app/account owner, operator, exact callback URL, and credential-file path on the operator's own machine. Never copy a secret into chat, logs, this document or git.
- A short start/expiry window, who stops the public listener, and how the temporary PayPal webhook registration is removed.
- A reviewed route-limited design: only bounded `POST /v1/paypal/webhook` traffic may reach the merchant service. The customer app, merchant UI, approval/reconcile routes, databases and arbitrary paths stay unexposed. Keep the default loopback behavior and signature verification intact; do not relax the global Host check to admit arbitrary public requests.
- The exact new synthetic sandbox case/capture and permitted refund amount. A real sandbox operation must be approved by the owner and clearly separated from fake payments. No real-customer records or live-money account may be used.

The required hosting/proxy change needs its own reviewed implementation and explicit lane authorization. Neither a tunnel nor a callback hostname is selected in this preparation.

## Delivery evidence required

After those prerequisites are satisfied, the operator registers the approved listener for the correct sandbox app and supplies its actual webhook ID. Generate the agreed sandbox refund, retain the observed event ID and delivery status, and confirm the server's signature-verification result. The merchant may settle only after provider read-back agrees on the refund ID, completed status, amount, currency and operation custom_id. Compare the stored merchant case and customer status; preserve failures, mismatches and retries.

Record environment, commit, subscribed event type, redacted callback identity, refund/event IDs, verification and read-back outcomes, timestamps and cleanup. Do not claim delivery from a local stub, a simulator alone, an API-reachable health endpoint or an unrelated historical refund report. Do not treat a deliberately generated delivery as a new human evaluation.

After the test, remove the temporary subscription and public access, verify the public route is closed, and retain only the agreed redacted evidence outside secret-bearing files. Final demo recording is a separate deferred task.
