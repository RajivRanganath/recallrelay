# 6 November 2026: resolution-status continuation

Continues from `a8484dd` on Rajiv's existing evidence branch. The checkpoint's status client had socket inactivity timeouts: a peer sending headers or body bytes slowly could extend waiting indefinitely. Both new trickle regressions failed against the unchanged checkpoint implementation and pass against the supervised client. The new design terminates/reaps stalled child workers after the configured local wait and rejects excess work at a two-worker per-client limit. Cleanup adds to the configured wait; this is a local dependency-wait bound, not a production availability guarantee.

HTTP framing is now checked before parsing the bounded response: duplicate lengths/types, conflicting Content-Length/Transfer-Encoding, unsupported/repeated transfer encodings, and invalid lengths fail closed. Valid chunked and connection-delimited JSON still work. No new runtime dependency or v1 field change was needed.

Observed focused checks: 13 resolution client/integration tests passed. Full customer-to-mock HTTP checks verify the unchanged committed mock, seven authored contract statuses, visible sanitized failures, manual assessment during dependency failure, and no evidence mutation from status reads. Synthetic status relay, including `refunded`, is not merchant integration or payment evidence. The current continuation does not call OmniRoute or a payment provider, nor alter existing provider reports. Actual resolution integration, independently reviewed holdout, authentication, and final demo remain unfinished.

Final continuation checks: 78 evidence tests with ResourceWarnings treated as errors, 3 shared contract tests, 60 fixture-policy checks, dependency consistency, JavaScript syntax, and whitespace checks all passed. Changes remain local and uncommitted.

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
