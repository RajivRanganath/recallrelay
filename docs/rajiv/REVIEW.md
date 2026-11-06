# 6 November 2026: inbound request-limit continuation

Started `work/rajiv-request-limits` from merged main `c13ec97` after verifying PR #14 merged and its evidence/shared-contract CI passed. The local tree was clean. The resolution branch still points to the original scaffold; actual merchant integration cannot be established from it.

The prior socket inactivity timeout allowed an observed header trickle to take 6.05 seconds and still return HTTP 200. The evidence server now admits at most eight active handlers and enforces a ten-second total receive budget from handler setup through the complete body, including the request line and headers. Rejected excess connections receive a best-effort 503 then close before application work; split writers can instead see a connection failure. Deadline expiry interrupts reads and rejects/closes incomplete input before storage. Parseable timed-out requests attempt a 408 response; an actively uploading peer may instead observe a reset; malformed/incomplete lines may receive another parse error or close.

Completed input cancels the receive watchdog before validation/AI/storage work. A capacity slot lasts through response and connection cleanup. Shutdown joins admitted handlers and their watchdogs. These controls do not interrupt accepted work, provide a total application response deadline, bound CPU use or OS scheduling/backlog behavior, or establish production availability under sustained flooding. Existing upstream deadlines and synthetic-only boundaries still apply.

The nine new local regressions cover trickling lines/headers/bodies, a shared header/body receive budget, concurrent admission and excess rejection before storage, accepted work completing beyond the receive deadline, recovery after invalid/disconnected requests, and shutdown cleanup. Authored traffic, short test budgets and temporary SQLite databases only; no live AI, payments, credentials, provider-report changes, shared contract changes or resolution-lane changes.

Follow-up review reproduced a shutdown failure after an injected handler-thread start failure: the inherited registry tried to join an unstarted thread. The server now tracks only successfully started workers and releases admission capacity after a failed start; two added regressions verify clean shutdown and recovery. A rerun also observed socket resets while a peer kept trickling data after rejection. The trickle tests accept a bounded rejection or reset, still reject successful responses, verify ongoing traffic before expiry, and check no persistence and recovered capacity.

Final local verification on Python 3.11.16: 92 evidence tests with ResourceWarnings treated as errors, 4 Node UI tests, 3 shared-contract tests, the unchanged 1-test resolution starter suite, and 12 fixture cases / 60 policy checks passed. All nine focused request-limit tests passed, including injected worker-start failure and shutdown cleanup. JavaScript syntax, dependency consistency and whitespace checks passed. Existing pinned dependencies were reused; no fresh install, browser recheck, live-provider evaluation or production load test is claimed. Hosted CI is reported separately from these pre-commit local checks.

Actual resolution integration, merchant handoff, independent holdout labels, authentication/private-data support and a recorded demo remain pending. Git records the commit and publication status of this continuation.

---

# 6 November 2026: critical review of the full evidence lane

Scope: current branch `work/rajiv-provider-http-validation`, including assessment rules, storage, image/JSON intake, inbound and upstream HTTP boundaries, extraction, UI state, evaluation code/reports, evidence CI, and the frozen contracts read-only. The review did not change the resolution lane, shared contracts/mocks/tests, or root configuration. This record describes the feature-branch changes and their pre-commit validation.

## Additional findings reproduced and fixed

1. **Ambiguous inbound headers could still save an assessment.** Six raw HTTP cases returned 200 before the fix: duplicate JSON Content-Type, conflicting Content-Type, duplicate Origin with a later foreign origin, an empty Origin, empty Transfer-Encoding, and an empty first transfer header hiding a later chunked header. POST now requires one JSON Content-Type, at most one exact same-origin Origin when supplied, no Transfer-Encoding headers, and one ASCII decimal length. The regression verifies 400/403 responses and no persisted assessment. Origin/Host checks remain request guards, not service authentication.
2. **Late configuration could disable suggestions or overwrite provenance.** Preparing a photo before `/health` completed left suggestions disabled; a late AI configuration response also overwrote a loaded mock sample's source note. Unknown health modes were presented as mock. Three asynchronous state regressions failed before the fix. Configuration now accepts only mock/ai, reconciles controls with the current busy state, preserves the current proposal note, and visibly reports unavailable configuration while leaving typed entry usable. A fourth regression confirms configuration completion cannot unlock a busy operation. These dependency-free Node tests now run in evidence CI.
3. **The live evaluation command could succeed despite wrong fields.** An offline adapter returned B999 for the eligible clear-label reference: one field mismatch, an excluded outcome, no false eligibility, and no unavailable call; the command previously exited successfully. It now writes the full report and exits nonzero on any field mismatch as well as unavailable/false-eligible results. Tests cover both failing and matching CLI outcomes without provider calls. Conservative abstentions against a non-null authored reference also count as field mismatches; the report retains the distinction.

The preceding gateway fix was also rechecked: all twelve malformed-response variants fail closed, valid framing still succeeds, and the targeted checks retain no child workers or automatic retries.

## Final observed verification

A temporary source-only export containing the current edits and new test file passed 83 evidence tests on Python 3.11.16 with ResourceWarnings treated as errors, 4 Node UI tests, 3 shared contract tests, the unchanged 1-test resolution starter suite, and 12 fixture cases / 60 policy checks. JavaScript syntax, dependency consistency, and whitespace checks passed. The export used the existing pinned interpreter; this was not a fresh network dependency install. No ignored database or virtual environment was copied. Basic credential-pattern scanning found no matches in tracked/unignored text files; this is not a comprehensive secret or dependency-vulnerability audit. The updated CI step was exercised locally, not by a new hosted CI run.

An actual in-app browser check against a temporary mock-mode evidence server verified sample provenance, separate confirmation, a manual matching assessment, edit invalidation, unresolved blank-batch clarification, and a visible status dependency failure. The delayed-health cases used deterministic DOM doubles, not browser network interception. The browser check did not cover live AI, every viewport, or full accessibility. No provider credentials were read and no live AI/payment calls were made in this review; previous provider reports remain unchanged.

## Material work still pending

- Actual resolution-service integration, canonical merchant handoff, and recorded demo. The current service source/branch is a scaffold; mock HTTP success cannot establish those outcomes.
- Separately reviewed holdout labels, broader provider injection evaluation, and any human completion/savings study. The 12-case provider report was used during development; its 24 matching fields are not general accuracy or calibrated-confidence evidence.
- Authentication and authorization, private real-data handling, and operational request limits before any real-data use. The current loopback threaded server has an inactivity timeout, not an application-wide inbound request deadline or bounded HTTP thread pool. No production availability claim follows from the bounded upstream clients.

---

# 6 November 2026: AI gateway response-validation continuation

Started `work/rajiv-provider-http-validation` from merged main `601773f` after verifying evidence PRs #11–#13 were merged. The prior 78-test evidence suite passed before edits. This review found that the OmniRoute worker's response-header checks were weaker than the resolution client's: duplicate Content-Type and unsupported/repeated Transfer-Encoding could be accepted with an otherwise usable JSON proposal.

The focused regression reproduced seven accepted malformed response variants against the unchanged gateway client. The updated worker rejects them before parsing proposal JSON. All twelve malformed-header variants now produce sanitized `invalid_response` failures without retries or remaining child workers. Positive checks preserve length-delimited, chunked, and connection-delimited JSON, including capacity recovery on the same adapter after a rejected response. The focused gateway/evaluation module passed all 15 tests.

Final continuation verification on Python 3.11.16: all 80 evidence tests passed with ResourceWarnings treated as errors; 3 shared contract tests and 12 fixture cases / 60 policy checks passed. Dependency consistency, JavaScript syntax, and whitespace checks passed. The initial shared-test attempt could not bind its mock socket in the read-only sandbox; it passed after rerunning with loopback access. Temporary storage and loopback tests required access beyond that sandbox.

The gateway is an authored loopback test server with a synthetic key; this work does not measure live gateway compatibility, image recognition, model injection resistance, or provider availability. The prompt, model/request settings, credential sources, and recorded provider development reports remain unchanged. Actual merchant-service integration and independently reviewed holdout evaluation remain pending. At this earlier stage the changes were local; the full continuation is recorded in the critical review above.

---

# 6 November 2026: resolution-status continuation

Continues from `a8484dd` on Rajiv's existing evidence branch. The checkpoint's status client had socket inactivity timeouts: a peer sending headers or body bytes slowly could extend waiting indefinitely. Both new trickle regressions failed against the unchanged checkpoint implementation and pass against the supervised client. The new design terminates/reaps stalled child workers after the configured local wait and rejects excess work at a two-worker per-client limit. Cleanup adds to the configured wait; this is a local dependency-wait bound, not a production availability guarantee.

HTTP framing is now checked before parsing the bounded response: duplicate lengths/types, conflicting Content-Length/Transfer-Encoding, unsupported/repeated transfer encodings, and invalid lengths fail closed. Valid chunked and connection-delimited JSON still work. No new runtime dependency or v1 field change was needed.

Observed focused checks: 13 resolution client/integration tests passed. Full customer-to-mock HTTP checks verify the unchanged committed mock, seven authored contract statuses, visible sanitized failures, manual assessment during dependency failure, and no evidence mutation from status reads. Synthetic status relay, including `refunded`, is not merchant integration or payment evidence. The current continuation does not call OmniRoute or a payment provider, nor alter existing provider reports. Actual resolution integration, independently reviewed holdout, authentication, and final demo remain unfinished.

Final continuation checks: 78 evidence tests with ResourceWarnings treated as errors, 3 shared contract tests, 60 fixture-policy checks, dependency consistency, JavaScript syntax, and whitespace checks all passed. These changes were subsequently committed as `82ad673` and merged through PR #13.

---

# Historical checkpoint: 6 November 2026 OmniRoute continuation

The pushed 5 November checkpoint was rechecked: all 57 original evidence tests passed. The local continuation adds an opt-in image adapter using the existing IIT KGP OmniRoute key source, with no copied credentials or new runtime dependencies. Default extraction remains mock; v1 assessment fields and deterministic confirmation remain unchanged.

Critical findings and fixes in this continuation:
- The UI previously hardcoded mock extraction and an 8-second request timeout. It now reads configured mode, labels AI proposals separately, and allows the backend's supervised call to finish. Health describes configuration, not reachability.
- An HTTP success alone did not establish usable extraction. Truncated generation, refusals, tool-call output, malformed JSON, and invalid proposals fail closed.
- Auto/smart did not produce usable image proposals in the initial three-case run. A diagnostic observed HTTP 429. An explicit vision route returned HTTP 200 with finish_reason length at a small token budget. After revising generation settings and the prompt, the final development run returned 12/12 proposals matching all 24 authored reference fields.
- Spawned workers enforce a bounded local wait even for trickling responses; stalled workers are terminated and reaped. That does not cancel accepted upstream work or establish billing guarantees.
- Gateway payload logging is separate from application logging. The startup no-log environment attempt did not take effect; the reused key's persisted no_log flag was enabled, and five earlier payload artifacts from this session were removed while preserving summaries and older history. Later observed gateway calls stored no payload artifacts.

Observed final checks: 70 evidence tests; 3 shared contract checks; 60 fixture-policy checks; dependency consistency, JavaScript syntax, and whitespace checks. Chrome checked confirmation and failure behavior with explicitly stubbed AI responses; live-provider results were captured separately. See [current runbook](RUNBOOK.md).

The final live run is a tuned synthetic development smoke, not a reviewed holdout, human study, calibrated-confidence result, production claim, or general prompt-injection guarantee. Actual resolution-service integration, authentication, real-data storage, independent evaluation, and final demo remain pending. Changes were verified locally before this feature commit.

---

# Historical review: 5 November 2026

The following records the prior checkpoint and its limits at that time.

# Critical review and next-stage verification

5 November 2026. Rajiv's feature branch: `work/rajiv-evidence-intake`. Review covers the local synthetic prototype, not a production or live-provider release.

## Findings fixed before moving on

1. **Image validation accepted header-only fakes.** The prior test even documented this acceptance. Replaced signature-only checks with restricted PNG/JPEG identification, integrity verification, reopen-and-load pixel decoding, single-frame enforcement, 4096-pixel edge and 8-million-pixel caps. Tests cover header-only data, truncation, MIME mismatch, animation and dimensions. Bytes stay transient. This follows the distinction between `verify()` and pixel loading in the [Pillow Image documentation](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify); it is not a malware or authenticity guarantee.
2. **Duplicate JSON keys were silently accepted.** An HTTP request containing two conflicting schema versions returned 200 in the regression run. Both inbound requests and upstream resolution responses now use strict JSON parsing; duplicate keys, non-finite constants, overflowing numeric exponents, malformed encoding and excessive nesting fail closed. Ambiguous Content-Length headers and incomplete request bodies are also rejected.
3. **Partial HTTP successes could masquerade as full status responses.** A 206 response containing otherwise schema-valid data was accepted before the fix. The client now requires 200, enforces declared/body size consistency and maps HTTP framing exceptions to visible dependency failures. A truncated body with valid JSON is covered as well as malformed JSON and wrong-case responses.
4. **Mock proposal output shared mutable lists.** Refactored the three original sample controls through the new normalizer so callers cannot mutate another proposal's uncertainty fields.
5. **Runtime verification did not match CI.** Created an ignored evidence-only Python 3.11 environment, pinned direct and transitive runtime packages in this lane, and ran the tests there. No root runtime dependency or other-lane environment was changed.

The initial adversarial run reproduced three failing cases (header-only image, duplicate JSON keys and partial HTTP success). Final regression coverage also includes valid-JSON truncation, HTTP framing, immutable history and concurrent repeats. Findings were fixed before the next-stage fixture UI was verified.

## Next stage implemented

- Provider-neutral extraction protocol and strict lane-local field-output schema, without campaign/order/database/payment capabilities.
- Conservative proposal filtering with one deterministic clarification. Explicit uncertainty, low/missing confidence and ambiguous identifiers stay blank. The 0.85 confidence threshold is an uncalibrated test policy.
- Exact-byte fixture adapter in `mode: mock`. Unknown images or adapter errors produce a sanitized unavailable result and leave typed entry available. No live provider is selected or contacted.
- Customer image-suggestion control with separate confirmation. Proposals do not create assessments. Final confirmed-text decisions remain deterministic and labeled `manual`.
- Twelve versioned, fictional PNG/JPEG image variants plus a hash-checked policy replay and authored typed-entry baseline. The report records 12 cases / 60 checks / zero failures in fixture mode.

## Observed verification

- Python 3.11.16: 57 evidence tests passed with ResourceWarnings treated as errors.
- A temporary source-only export also passed all 57 evidence tests, the fixture replay and JavaScript syntax checks. It contained no ignored database, virtual environment or upload fixtures. It used the already installed, pinned evidence interpreter; it was not a fresh network install or public deployment.
- Shared contract suite: 3 tests passed. Unchanged resolution starter suite: 1 test passed. This does not certify Vismaya's future implementation or payments.
- `pip check`, JavaScript syntax and whitespace checks passed.
- Browser: uploaded conflicting-batch fixture → model suggestion, blank batch, one clarification, fresh confirmation required → `needs_information`. Replacing the image cleared the old proposal/result/confirmation. Unknown synthetic image → visible extraction unavailable, blank fields and usable typed entry; no browser console warnings/errors in that observed flow.
- Branch fast-forwarded to the already committed `origin/main` task-link documentation update; no new shared-file edit was authored. Working changes remain restricted to Rajiv's lane and evidence CI.

## Remaining limits

This is still a mock-first local prototype. There is no actual OCR/model extraction, measured model confidence, genuine image-recognition accuracy, human completion study, real-provider prompt-injection result, authentication, persistent private image store, automatic merchant handoff, live integration, payment execution or deployment. The resolution client uses socket inactivity timeouts; it is not a guaranteed total request deadline against an indefinitely trickling upstream. Local assessment replay/concurrency checks are not an exactly-once guarantee.

Next live-model work needs an account-owner-approved provider/cost setup. Preserve the fixture/manual paths, capture actual provider model/version/configuration, and evaluate genuine outputs on a separately reviewed holdout set. Keep v1 unchanged while working only in the evidence lane.
