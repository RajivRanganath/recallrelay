# Rajiv's evidence runbook

Current continuation: `work/rajiv-study-report`, based on merged PR #23 / main `829501c`. Use `evidence/.venv/bin/python -B -m evidence.evals.study_report --sessions PATH --trials PATH --output NEW_JSON` to check and summarize returned timing records offline. See [HUMAN-EVALUATION.md](HUMAN-EVALUATION.md) for exact fields, denominators and limits. Ten focused synthetic-record checks and unchanged development-v2 plan verification passed locally; header-only input produced zero observations. This does not supply human measurements or independent labels.

## Previous checkpoint: completion preparation

Current checkpoint: 8 November 2026, `work/rajiv-completion-prep`, based on merged PR #20 / main `7c78d14`. [COMPLETION.md](COMPLETION.md) maps all five Rajiv tasks, records a fresh dependency install and clean-source verification, and gives the remaining human/demo actions. [HUMAN-EVALUATION.md](HUMAN-EVALUATION.md) supplies a prospective protocol and blank data sheets. No human observations or new provider results are present.

The merged implementation passed 130 evidence tests with actual review/status integration against current unmerged resolution `3be76f2`, seven Node UI checks, 60 fixture policy checks, plan verification and dependency consistency. The exported customer app passed the mock browser rehearsal and stopped normally. See the completion checkpoint for exact scope and reproducibility; hosted checks from this preparation are separate.

## Previous checkpoint: report output reservation

Checkpoint: 8 November 2026. Branch: `work/rajiv-eval-output`, based on merged main `e55f431`. PR [#19](https://github.com/RajivRanganath/recallrelay/pull/19) is merged and its evidence/shared-contract checks passed. Git records this continuation's commit/publication status.

## Current continuation: report output reservation

Planned and unplanned provider evaluation commands now reserve a new report file before reading a key or extracting. Existing files/directories/symlinks, invalid parent paths and competing claims fail before provider work. Later write/close errors are visible and do not retry calls. A configuration failure can leave an empty reserved file; interruption or later I/O failure can leave incomplete output. This does not provide atomic writing, journaling, crash recovery or cancellation of accepted upstream work. Always select a fresh path for a new attempt.

The current offline setup is `evidence/evals/plans/development-v2.json`. The unchanged v1 plan is historical and intentionally rejects the changed evaluator hash. No provider results, references or fixture bytes were rewritten, and no new provider result is claimed. See [the evaluation instructions](EVALUATION.md) for exact behavior and limits.

Local verification on Python 3.11.16: 130 evidence tests passed with ResourceWarnings treated as errors and actual-service integration enabled, including seven new output-path/competing-run/cleanup regressions. Seven Node UI tests, three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, new development-v2 plan verification, dependency consistency and whitespace checks passed. The unchanged v1 plan correctly rejected the new evaluator source. Existing pinned dependencies were reused; no provider credentials, live AI/payment calls, fresh dependency install or new browser check were used. Hosted CI is reported separately.

Human reference review and effort measurement, holdout protocol work, and the jointly recorded demo remain pending. Historical sections below retain their original scope.

## Previous checkpoint: offline development-reference review

The following records `fea0c71`, merged through PR #19.

Use `evidence.evals.review prepare --output NEW_DIRECTORY` to export a blank standalone form with hash-checked images and a packet identity record. An actual person supplies field observations and a reviewer declaration, then downloads JSON locally. `review check --packet PATH --review PATH --output NEW_REPORT` validates complete self-reported coverage and preserves disagreements against authored references. It never rewrites labels or enables holdout/human-validation flags. See [the review instructions](LABEL-REVIEW.md).

The twelve-image packet is available locally under ignored `evidence/.local/label-review-development-v2/`. Browser QA reset it to fully blank after checking input state changes; its declaration is unchecked. No completed human record exists from this continuation. These remain previously visible development images, not a new holdout. A person must now review them, and disagreements require adjudication before any revised reference set.

Local verification on Python 3.11.16: all 123 evidence tests passed with ResourceWarnings treated as errors and actual-service checks enabled, including nine new offline review tests. Seven Node UI tests (three new), three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, committed development-plan verification, dependency consistency, workflow YAML parsing and whitespace checks passed. Existing pinned dependencies were reused. Hosted checks are reported separately; no fresh install, live-provider run or human review is claimed.

## Previous checkpoint: one-command customer rehearsal

The following records `f9ae35b`, merged through PR #18.

Run `evidence/.venv/bin/python -B -m evidence.demo` after installing the evidence lock file. Open the printed loopback URL. The actual customer app starts with mock fixture extraction, the committed resolution mock and fresh temporary storage; Ctrl+C stops owned servers and deletes that state. Provider/resolution environment variables do not silently select live adapters. An explicit `--resolution-url http://127.0.0.1:8102` reads an already-running local service and leaves its lifetime to its owner. See [the customer demo outline](DEMO.md) for clean-start commands and the first 75 seconds.

The browser walkthrough covered separate confirmation, matching manual assessment, unresolved blank batch, excluded batch and simulated merchant status. The launcher exited cleanly via Ctrl+C. Mock resolution now uses a mode label valid for both the canned mock and saved reviews from the actual mock-mode service, while preserving the separate-record warning.

Local verification on Python 3.11.16: 114 evidence tests passed with ResourceWarnings treated as errors and actual-service checks enabled, including four new launcher checks. Four Node UI tests, three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, frozen development-plan verification, dependency consistency, JavaScript syntax and whitespace checks also passed. Existing pinned dependencies were reused; this is not a fresh network install or a new provider evaluation. Hosted checks are reported separately.

A jointly recorded demo, merchant UI, sandbox payments, independently reviewed holdout labels and human measurement remain pending. Historical sections below retain their original checkpoint scope.

## Previous checkpoint: actual resolution review/status integration

The following records `565958e`, merged through PR #17.

The resolution branch now contains an actual review/status service at `e1e16be6928afcdd52015097a3bbab6b42ddbd8b`; it is no longer only the original scaffold. Six new evidence-owned opt-in checks run that exact source in an isolated subprocess, use its actual evidence HTTP client, explicitly hand off a synthetic assessment/order/remedy snapshot, and read its status through the customer backend. Separate temporary databases remain service-owned. A payment-denying test adapter records any refund attempt and causes a test failure if called; subprocesses inherit no provider keys.

Focused local verification passed all six tests on Python 3.11.16 with ResourceWarnings treated as errors. Scenarios include eligible/manual/missing/excluded review, remaining amounts and old orders, immutable handoff snapshots after evidence edits, mismatched cases, and visible dependency failure with typed entry still usable. See [the integration runbook](INTEGRATION.md) for the exact commit, reproduction and limits. Evidence CI pins that resolution commit in a separate checkout; its hosted result is separate from local checks.

This verifies actual synthetic review/status compatibility, including an explicit test-coordinator handoff. Merchant UI, approval/refund execution, PayPal sandbox integration, jointly reviewed integration and recorded demo remain pending. No live AI/payment call, credential read, other-lane edit or contract change occurred. Historical checkpoint sections below retain their original scope and pending-work statements.

Local verification on Python 3.11.16: all 110 evidence tests passed with ResourceWarnings treated as errors, including all six actual-service checks enabled against the pinned export. The four Node UI tests, three shared-contract tests, unchanged one-test resolution starter suite, 12-case / 60-check fixture replay, committed development-plan verification, dependency consistency, JavaScript syntax and whitespace checks also passed. Existing pinned dependencies were reused; no fresh install, hosted CI run, browser recheck, live-provider evaluation or human study is claimed.

## Previous checkpoint: frozen development evaluations

The following records `8b19eb5`, merged through PR #16.

The evaluator now validates synthetic references and their typed decisions before provider calls. Offline plan creation/checking reads no credentials. Planned live runs verify the manifest/images, source/schema/lock hashes, selected case order, provider/model/URL/timeout and Python/Pillow/jsonschema versions before reading a key; reports retain the checked snapshot and plan fingerprint. Model/timeout/case overrides must match and planned output cannot overwrite an existing report. Existing unplanned commands remain supported.

The committed [development plan](../../evidence/evals/plans/development-v1.json) was created and checked offline for all twelve current fixtures. It is not a provider result, human review or holdout. Earlier provider reports remain unchanged. See [the evaluation runbook](EVALUATION.md) for the offline commands and opt-in provider replay. No credentials were read and no live AI or payment calls were made in this continuation.

Local verification on Python 3.11.16: 104 evidence tests with ResourceWarnings treated as errors (including 12 new offline evaluation-plan tests), 4 Node UI tests, 3 shared-contract tests, the unchanged resolution starter test, and 12 fixture cases / 60 policy checks passed. The committed development plan was created and verified offline. Dependency consistency, JavaScript syntax and whitespace checks passed. Existing pinned dependencies were reused; no fresh install, browser recheck, live-provider run or human study is claimed. Hosted CI is reported separately from these pre-commit local checks.

## Previous checkpoint: inbound request limits

The following records `work/rajiv-request-limits`, based on `c13ec97`, committed as `af1600c` and merged through PR #15.

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
