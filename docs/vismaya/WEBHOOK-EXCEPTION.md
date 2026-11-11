# Proposal: temporary sandbox webhook verification (AGENTS.md exception)

**Status: DRAFT. Nothing in this document has been run.** Written 11 November 2026 for review by both contributors.

## What is and is not authorized right now

Rajiv's statements, as relayed by Vismaya in chat and quoted here so the record is in the repository (Rajiv should also record them on the pull request that carries this file):

1. He approves a temporary, sandbox-only PayPal webhook verification exercise and grants a specific exception to AGENTS.md's no-public-deployment rule for this test, with these limits: only the webhook route may be publicly reachable; synthetic data and sandbox payments only; credentials stay outside the repository and logs; the tunnel is stopped and the temporary webhook registration removed after verification; both contributors confirm the proposal before the tunnel starts.
2. He approves saving this proposal and preparing the merchant server changes on a feature branch for review.
3. He states that this does **not** yet authorize installing or starting a tunnel, registering a public webhook, or performing the sandbox refund. The implementation and execution plan are to be confirmed separately, and the generated callback URL must be confirmed before registration.
4. He states that he explicitly authorized the merchant-lane exceptions for PRs #30 and #33 in his project chat.

Until the confirmations at the end of this file are filled in, the only permitted work is writing this proposal and the reviewed server change described below.

## Purpose

Real PayPal webhook delivery has never been verified. The route, PayPal's signature check and the operation-bound settlement rule exist and are tested only with fakes and a local stub (see RUNBOOK). This exercise would show, once, whether a real sandbox event is delivered, verified by PayPal's verification API, and settles a matching pending refund. It proves nothing about production, other event types or load.

## Callback URL

`https://<TUNNEL_HOST>/v1/paypal/webhook`

`<TUNNEL_HOST>` does not exist yet. It is generated when the tunnel starts. It is filled in below, and both contributors confirm that exact URL, before anything is registered with PayPal. Only the route `POST /v1/paypal/webhook` on that one host is meant to be public. No other host, path or method is.

## Server changes (implemented on a feature branch; no tunnel needed to test them)

New options on `python -m resolution.backend.server` (all off by default):

- `--paypal-webhook-public-host HOST`: the one public DNS name of the tunnel. It must be a plain DNS name (no scheme, port, path, IP address or localhost). Needs `--paypal sandbox` and `--paypal-webhook-id`.
- `--paypal-webhook-window-minutes N`: how long the public host is served after startup (1 to 120, default 30).

Behaviour:

- A request whose `Host` header equals the configured name exactly (case-insensitive, one Host header, no port) may reach **only** `POST /v1/paypal/webhook`, **exact path** (no query string, no trailing slash), and only while the window is open. Everything else on that host (pages, health, case data, every other route, every GET) is refused with 403 before any handler runs.
- After the window closes, the public host gets 403 for everything. Loopback keeps working.
- Any other non-loopback host is refused as before. A request with two Host headers is never trusted.
- The webhook handler is unchanged: JSON body, bounded size, browser-style cross-origin requests refused, PayPal's own verification API must answer SUCCESS before anything changes, and the refund must be read back from PayPal and carry the operation's `custom_id` before a pending (or wrongly failed) case can become refunded.
- Note: Python's built-in server collapses extra leading slashes (`//v1/paypal/webhook` becomes `/v1/paypal/webhook`). That is the same single route and is still verified. It is covered by a test.
- Tests: `resolution/tests/test_public_webhook.py` (12 tests).

## Credentials

The sandbox credentials stay in the existing file outside the repository (`C:\Users\VISMAYA\secrets\paypal.env`), read for two named variables only. The webhook ID is not a secret but is passed on the command line and not committed. The server logs nothing, and no value is printed or copied into the repository, issues or chat.

## Execution plan (to be confirmed separately; do not run)

Who: **Vismaya** does the PayPal dashboard login, the buyer approval and starts and stops the tunnel (a person must do these). **Claude** prepares and runs local checks and any throwaway launcher. **Rajiv** reviews the server pull request and confirms the URL and the results.

1. Review and merge the server pull request.
2. Start the server on loopback with **no** public options. With no public host configured, every public request is refused, including the webhook.
3. Start a temporary tunnel to `http://127.0.0.1:8102` (suggestion: a Cloudflare quick tunnel, `cloudflared tunnel --url http://127.0.0.1:8102`, which needs no account; downloading it needs explicit permission). Record the generated host here, and both confirm the exact URL.
4. In the PayPal Developer dashboard (**Sandbox**), register a webhook at that URL for `PAYMENT.CAPTURE.REFUNDED` only. Copy the webhook ID.
5. Restart the server with `--paypal sandbox --paypal-env <env file> --paypal-webhook-id <ID> --paypal-webhook-public-host <TUNNEL_HOST> --paypal-webhook-window-minutes 30`. The window starts now.
6. **Negative checks:** a forged POST to the public URL returns 401; `/`, `/health`, `/v1/cases` and every other path on the public host return 403.
7. **Positive check:** run a throwaway launcher outside the repository that wraps the real sandbox adapter and drops the refund response after PayPal accepts it, so the case stays pending. Make a fresh sandbox payment (the buyer approves it), load the case, approve the refund (it shows "Refund pending"), and wait for PayPal's real event. Expected: the server verifies it with PayPal, reads the refund back, matches the operation ID, and the case becomes "Refunded" without pressing "Check refund again".
8. **Replay:** resend the same event from the dashboard. Expected: accepted, no change.
9. Record the exact results, including any failure.

Optional, informational only: PayPal's dashboard simulator events are expected to fail verification; whatever is observed is recorded as observed.

## Pass criteria

The forged event is rejected; every other public path is blocked; the real event settles only the matching pending case; a replay changes nothing; nothing sensitive appears in any log or file.

## Cleanup (all steps, in this order)

1. Stop the tunnel process.
2. Delete the webhook registration in the PayPal Developer dashboard.
3. Stop the server; delete the throwaway launcher and its temporary database.
4. Confirm the old tunnel URL no longer answers.
5. Confirm no webhook ID, URL or credential was written to the repository.
6. Record the results and the end of the exception in `docs/vismaya/RUNBOOK.md` and `LIVE-CHECKS.md`. The public-host option stays off unless explicitly used.

## Risks and limits

- A public endpoint receives internet traffic. Mitigations: an unguessable random host, one route only, PayPal verification before any state change, a body size cap, a short window, sandbox and synthetic data only, no logging.
- The tunnel provider can see the (synthetic sandbox) payloads.
- Server-side route restriction is the control; the tunnel is not trusted to filter paths.
- One delivery on one machine proves little about reliability, retries or ordering.

## Expiry

The exception ends when the cleanup above is complete, or at the end of the session in which the test is run, whichever is first. Any further public exposure needs a new written approval.

## Confirmations (blank until filled in by each person, on the pull request)

- [ ] Rajiv confirms this proposal and the server change as reviewed: ______
- [ ] Vismaya confirms this proposal and the server change as reviewed: ______
- [ ] Both confirm the generated callback URL before registration: `https://________/v1/paypal/webhook`
- [ ] Cleanup completed and recorded: ______
