# Rajiv's evidence runbook

Checkpoint: 6 November 2026. Branch: `work/rajiv-request-limits`, based on merged `origin/main` commit `c13ec97`. PR [#14](https://github.com/RajivRanganath/recallrelay/pull/14) was verified merged; its evidence and shared-contract CI passed. Git records the commit and publication status of this continuation.

## Current continuation: inbound request limits

Reproduced on the merged checkpoint: a request trickling header bytes for 6.05 seconds still received HTTP 200 despite the five-second socket inactivity timeout. The evidence server now uses a non-blocking eight-handler admission cap and a single ten-second receive deadline covering the request line, headers and body. An excess connection gets a best-effort JSON 503 then closes before application work. A client still writing may see a connection failure instead. Expired input is rejected/closed before assessment persistence; parseable timed-out requests attempt a 408 response; an actively uploading peer may instead observe a reset.

Each admitted handler owns one receive watchdog. Completed input cancels it before JSON/image validation, AI or storage processing; cleanup joins it, releases capacity and closes the connection. Server close waits for admitted handlers. This does not cancel or roll back accepted application work and is not a total response deadline or production availability guarantee. Slow CPU work, OS scheduling/backlog behavior and sustained flooding are not bounded by the receive budget.

Focused local tests use shorter budgets, temporary databases and loopback sockets. They cover trickling lines/headers/bodies, one shared header/body budget, two admitted concurrent assessments with further requests rejected before storage, completion after the receive budget, disconnected/rejected-request recovery, and shutdown joining an incomplete request. No live AI/payment calls or credentials are used. Actual merchant integration, independent holdout review, authentication/private-data support and the recorded demo remain pending. Only evidence code/tests/docs and Rajiv documentation change.

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_request_limits.py' -v
```

Follow-up review reproduced a shutdown failure after an injected handler-thread start failure: the inherited registry tried to join an unstarted thread. The server now tracks only successfully started workers and releases admission capacity after a failed start; two added regressions verify clean shutdown and recovery. A rerun also observed socket resets while a peer kept trickling data after rejection. The trickle tests accept a bounded rejection or reset, still reject successful responses, verify ongoing traffic before expiry, and check no persistence and recovered capacity.

Final local verification on Python 3.11.16: 92 evidence tests with ResourceWarnings treated as errors, 4 Node UI tests, 3 shared-contract tests, the unchanged 1-test resolution starter suite, and 12 fixture cases / 60 policy checks passed. All nine focused request-limit tests passed, including injected worker-start failure and shutdown cleanup. JavaScript syntax, dependency consistency and whitespace checks passed. Existing pinned dependencies were reused; no fresh install, browser recheck, live-provider evaluation or production load test is claimed. Hosted CI is reported separately from these pre-commit local checks.

## Previous checkpoint: merged HTTP and UI review

The following sections retain the pre-commit checks for `ef8d93e`, subsequently merged through PR #14. The earlier continuation was based on `601773f`; PRs #11–#13 were already merged.

## Critical follow-up review

The full-lane review also fixed six accepted ambiguous inbound-header variants, late-health UI state/provenance races, and a provider-evaluation exit status that ignored field errors when they did not cause false eligibility. The CLI now saves the complete report and fails any field mismatch. Details, reproduced failures, and material remaining gaps are recorded at the top of [the critical review](REVIEW.md).

Final source-only export verification: 83 evidence tests with ResourceWarnings treated as errors, 4 dependency-free Node UI state tests, 3 shared contract tests, the unchanged 1-test resolution starter suite, and 12 fixture cases / 60 policy checks all passed. JavaScript syntax, dependency consistency, and whitespace checks passed. The export reused the installed pinned interpreter; no fresh dependency install or hosted CI run is claimed. The actual browser check covered sample/confirmation, edit invalidation, missing-batch clarification, and visible dependency failure in mock mode. The asynchronous configuration regressions use DOM doubles. No new live AI calls were made and existing provider reports are unchanged.

Run the added UI checks with `node --test evidence/tests/test_web.js`; evidence CI now includes this command. This feature-branch checkpoint changes only `evidence/**`, `docs/rajiv/**`, and the owned `.github/workflows/evidence.yml`; Git records its commit and publication status. The previous 80-test gateway verification below records the stage before this critical follow-up.

## Earlier continuation: AI gateway response validation

The OmniRoute client now applies the same strict HTTP response checks as the resolution-status client: exactly one JSON Content-Type, no duplicate or conflicting length/transfer headers, only a single chunked transfer encoding when present, and a bounded ASCII decimal Content-Length. Invalid responses produce sanitized `invalid_response` failures; typed entry remains available. Valid length-delimited, chunked, and connection-delimited JSON responses remain supported. No prompt, model, request configuration, credential, provider report, or v1 contract changed.

Before changing the client, the new regression reproduced seven accepted malformed responses: duplicate JSON Content-Type, conflicting Content-Type, gzip transfer encoding, identity transfer encoding, empty transfer encoding, repeated chunked headers, and a gzip/chunked list. All twelve malformed-header cases now fail closed. Valid framing succeeds on the same adapter after a failure, confirming that capacity is released. Tests also check one upstream request per attempt and no remaining child workers. The focused gateway/evaluation test module passed all 15 tests using an authored loopback gateway and synthetic key; this continuation made no live AI calls.

Final continuation verification on Python 3.11.16: all 80 evidence tests passed with ResourceWarnings treated as errors; 3 shared contract tests and 12 fixture cases / 60 policy checks passed. Dependency consistency, JavaScript syntax, and whitespace checks passed. The initial shared-test attempt could not bind its mock socket in the read-only sandbox; it passed after rerunning with loopback access. Temporary storage and loopback tests required access beyond that sandbox.

The full continuation changes only `evidence/**`, `docs/rajiv/**`, and the owned `.github/workflows/evidence.yml`. The resolution branch still points to the scaffold, so actual merchant-service integration, independently reviewed holdout evaluation, and the recorded demo remain pending. No public deployment, merchant message, payment, contract change, or other-lane edit occurred.

Run the focused checks:

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_omniroute.py' -v
```

## Previous checkpoint: resolution status and mock integration

Committed as `82ad673` and subsequently merged through PR #13. This section records that checkpoint's verification; its source branch was `work/rajiv-evidence-intake`.

The status client now supervises the complete HTTP operation with a two-second local wait, followed by worker cleanup. This replaces socket-inactivity-only protection: trickling headers or body bytes can no longer keep the caller waiting indefinitely. Timeout/failure workers are terminated and reaped; the per-client two-worker limit rejects saturation without an upstream call. There are no retries, redirects, payment calls, or new runtime dependencies. Name resolution and HTTP reads run in the supervised child; schema and case-ID checks remain in the parent.

Response validation rejects duplicate Content-Length, conflicting length/transfer headers, unsupported or repeated transfer encodings, invalid/oversized lengths, and duplicate Content-Type. Valid JSON responses with one length, chunked framing, or connection-delimited framing remain supported within the response cap and wait limit.

Observed focused verification: 13 client/integration tests passed. Replaying the new slow-header and slow-body regression against the unchanged `a8484dd` client produced both expected failures; the updated client passes them and leaves no child worker behind. Full customer HTTP checks use temporary SQLite databases, the unchanged committed resolution mock, and authored response servers. They cover all seven v1 status values, sanitized 404/503 failures, no assessment creation/change from status reads, and usable manual assessment during dependency failures. Authored `refunded` output is only a relay test; no payment provider is called.

Final continuation verification on Python 3.11.16: all 78 evidence tests passed with ResourceWarnings treated as errors; 3 shared contract tests passed; the fixture replay passed 12 cases / 60 checks with zero failures. Dependency consistency, JavaScript syntax, and whitespace checks passed. Temporary-file and loopback access were required beyond the read-only sandbox. These changes were subsequently committed as `82ad673` and merged through PR #13.

Run just this continuation's integration checks:

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_resolution*.py' -v
```

Actual resolution-service integration, merchant handoff, independent holdout review, and recorded demo remain pending. Existing provider development reports are unchanged; this continuation made no live AI calls. The sections below retain the preceding OmniRoute checkpoint's setup and observed results; previously running processes must be checked before reuse.

## Run and demonstrate

Default fixture/manual mode still needs no keys:

```sh
evidence/.venv/bin/python -B -m evidence.backend.server
```

Opt-in local setup reuses the existing IIT KGP env file in place:

```sh
evidence/.venv/bin/python -B -m evidence.backend.server --port 8111 --db evidence/.local/omniroute-demo.sqlite3 --extractor omniroute --omniroute-env '/Users/rajiv/Documents/Projects/Project(kgp)/.env' --model gemini/gemini-3.1-flash-lite
```

The existing key was not copied, printed, committed, or replaced. Only `OMNIROUTE_API_KEY` is read from the selected file; other provider credentials are ignored. No IIT KGP source or env file was changed. The gateway's metadata setting `no_log` was enabled for this key, after a startup environment attempt did not take effect. Five payload artifacts created by this session's synthetic tests were removed; older history and status summaries were preserved. Later observed gateway summaries had no request, response, or pipeline payload artifacts.

The gateway and evidence demo were left running on loopback at ports 20128 and 8111 at this checkpoint. For a later gateway restart, use the installed CLI on loopback:

```sh
OMNIROUTE_SERVER_HOST=127.0.0.1 omniroute serve --no-open --no-tray
```

Verify the key's payload logging remains disabled before sending images. The gateway package observed locally was 3.8.49. The IIT KGP text setup uses `auto/smart`; it initially returned no usable image proposals here, including an observed HTTP 429. The explicit image route above returned served model `gemini-3.1-flash-lite`. Model IDs and bridge-header observations do not identify an immutable backend revision or prove no internal rerouting.

Upload a synthetic fixture → **Read label with AI** → review model/batch suggestions and any clarification → separately confirm → deterministic manual campaign assessment. Proposals do not persist assessments. Missing or conflicting identifiers remain unresolved. Try typed entry when extraction is unavailable. Sample controls remain explicitly mock even in the AI-configured app.

The unchanged resolution mock can run separately on 8102. The evidence client reads its canned status only; it does not create a merchant case or move money.

## Verification and results at the preceding OmniRoute checkpoint

Final observed evidence suite: 70 tests on Python 3.11.16 with ResourceWarnings treated as errors. Shared contract checks: 3 tests. Fixture-policy replay: 12 cases / 60 checks / zero failures, still mock. Dependency consistency, JavaScript syntax, and whitespace checks passed. Initial sandbox attempts could not create temporary files or bind sockets; verification used approved temporary-file/loopback access instead.

Chrome checked AI configuration labels, separate confirmation, manual assessment after confirmation, edit invalidation, 503 field clearing with typed entry, photo removal, and mock configuration labels. AI success/failure responses in that browser check were explicit stubs. No page errors were observed. Genuine model calls were evaluated separately.

Final genuine provider development run: 12/12 proposals, 24/24 fields matching authored typed-entry references, zero unavailable calls, zero false eligible simulated outcomes against those references. Dataset: synthetic-labels-v1; prompt: label-image-2; temperature 0, max_tokens 2048, reasoning_effort none where supported, 20-second supervised wait, no client retries. This previously visible development set was used during request tuning. It is not a reviewed holdout or general accuracy result.

Earlier reports remain: auto/smart 0/3 usable proposals at 512 tokens; explicit vision route 2/3 at 2048 tokens with the preceding prompt. A diagnostic observed HTTP 200 plus finish_reason length; those incomplete responses were rejected. See [evaluation scope](../../evidence/evals/README.md) and [final report](../../evidence/evals/reports/omniroute-development.json).

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -q
evidence/.venv/bin/python -B -m evidence.evals.run --check
evidence/.venv/bin/python -B -m unittest discover -s tests -q
node --check evidence/web/app.js
git diff --check
```

To repeat live calls, use the command in [evaluation instructions](../../evidence/evals/README.md) and a new report path. Preserve earlier reports, count unavailable calls, and inspect every field difference. Calls may consume provider quota.

## Remaining scope

Task 1 has a live image adapter and limited synthetic development evidence, including one instruction-bearing image; independently reviewed holdout and broader injection evaluation remain unfinished. Task 2 still lacks authentication and private real-data image storage. Task 3 remains synthetic; browser validation is bounded as described above. Task 4 still needs reviewed labels, holdout results, and a human study if making completion/savings claims. Task 5 still needs actual resolution-service integration, the daily integration check, and the recorded demo. None of the five full tasks is claimed complete.

Eligibility remains deterministic after human confirmation. Payment decisions, merchant approval, and resolution storage remain Vismaya's responsibility. No messages or calendar events were sent. Feature edits stay within `evidence/**` and `docs/rajiv/**`; contracts, mocks, root dependencies/docs, shared CI, and Vismaya's lane are unchanged.
