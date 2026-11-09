# 9 November 2026: completed live-AI human pilot

The participant completed all twelve typed and twelve actual AI-assisted tasks, with one real provider request per assisted task. Twelve proposals, zero unavailable extractions/failures/timeouts/withdrawals/retries. Median times were 8.0325 seconds typed and 4.8825 seconds assisted; all twelve pairs completed, with a 2.276-second median paired difference. Final field mismatches were zero on 48 comparisons; five needs_information results remained in each arm. No follow-up resolution-effort or independent clarification-appropriateness judgment was supplied.

Recovered actual browser autosaves, preserved the original journal and checked all task/image/source bindings and successful proposals against the actual-provider journal. OmniRoute requested gemini/gemini-3.1-flash-lite; all twelve replies reported gemini-3.1-flash-lite. Raw inputs remain local; the redacted report preserves all synthetic attempts and provider outcomes. This collection uses previously seen/timed development cases and fixed order; no holdout, general accuracy or causal savings claim follows. [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md) supplies full scope and provenance.

A hosted failure on the documentation update exposed an existing-test ENOTCONN cleanup race. PR #26 accepts only that already-disconnected shutdown state, preserving all recovery assertions and runtime. It is included in the evaluation branch; subsequent hosted evidence/shared checks passed. Results-artifact checks and later hosted runs remain separate from that earlier observation. No local automated test suite or extra provider smoke call was run in this continuation.

All standalone #1–#4 implementation/evaluation work is delivered for contributor acceptance. Issue #4 awaits the results PR's review/merge. Integration with the resolution lane and recording in #5 are deferred at the owner's request. Historical checkpoints below preserve the earlier pending states.

---

# 9 November 2026: human reference review and workflow results

Preserved the actual returned twelve-image review and Guided example note. The checker accepted all 24 identifiers with zero disagreements. Collected real interactions with the customer app using excluded practice, preloaded development images and browser monotonic timing. Human assistance was mock fixture lookup, separate from historical real-provider extraction.

All 24 distinct assigned tasks have a completed attempt across 25 retained records. First attempts comprise twelve typed completions, eleven assigned-mock completions and one accidental Stop click. Its completed 4.820-second retry remains separate. One assigned-assisted case did not request a suggestion and is disclosed. No completed identifier mismatch or false-eligible decision against authored references was observed. Five completed results per arm remained needs_information; follow-up resolution effort was not measured.

Validated downloads, schedule, source bindings, attempt chronology and report inputs; independently recalculated counts and medians. Published summaries omit aliases, private notes, raw identifiers and assessment IDs. Originals and instrumentation remain local. No runtime, contract, other-lane edit or new provider call occurred. Hosted CI is separate. [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md) states all deviations and limits; no holdout, general accuracy, causal savings or live-AI human timing claim follows.

Issues #1–#3 are closed with prototype acceptance notes. Task #4's mock development results are ready for contributor review, with live-AI human timing still required for its original comparison criterion. The separate collector is prepared; no AI task timings exist yet. #5 integration/recording remains deferred. Resolution PR #21 is now merged. Historical entries retain their original dates and scope.

---

# 8 November 2026: offline completion-effort reporting

Started `work/rajiv-study-report` from merged PR #23 / main `829501c`. Added `python -m evidence.evals.study_report` for the existing session/trial templates. It binds exact input/manifest and source hashes, validates session/case/mode identity and attempt chronology, rejects nonfinite/invalid timings and conflicting entered scores, and preserves first attempts, retries, noncompletion and missing pairs separately. Summaries remain per session; paired differences require both first attempts completed. Field errors, guessed absent fields, blank readable fields and false eligibility are recomputed against authored development references rather than trusted CSV scoring cells.

Reports omit aliases, free-text notes, provenance paths and raw final identifiers. Consent, configuration, timing and human effort remain self-reported; supplied provenance pointers are never opened. Human-validation/holdout flags stay false and adjudicated/validated session claims are rejected. Blank templates produce `no_observations`, not a study result. The command never calls a provider/payment service or reads a credential. Existing report paths cannot be overwritten; later I/O failure can still leave incomplete output.

Local verification: ten new synthetic-record tests passed on Python 3.11.16 with ResourceWarnings treated as errors, covering blank data, pairing, failed attempts/retries, private-field omission, separated modes, error recomputation, malformed records/times/CSV, false claims and output preservation. Development-v2 plan verification passed unchanged. An actual header-only CLI run saved an ignored `no_observations` tooling check with zero sessions/attempts. Documentation links, exact unchanged template headers and whitespace were checked separately. No full local suite rerun or new human/provider result is claimed; hosted CI is reported separately. Only evidence evaluation/tests/docs and Rajiv documentation change. Actual human observations, reference adjudication, separately reviewed new holdout data/reporting and the final joint recording remain pending.

---

# 8 November 2026: completion preparation and clean reproduction

From merged PR #20 / main `7c78d14`, prepared a Rajiv-only completion checklist, a prospective human review/timing/holdout protocol, header-only session/trial/adjudication sheets and an explicit customer-to-merchant recording transition. No human declarations, participant observations, holdout labels or video results were fabricated. A fresh blank review packet and local collection sheets are under ignored `evidence/.local/completion-prep-2026-11-08/`.

A clean source export and fresh Python 3.11.16 environment installed the evidence lock from PyPI. All 130 evidence tests passed with ResourceWarnings treated as errors and six actual-service checks enabled against current unmerged resolution commit `3be76f2`. Seven Node UI checks, 12 fixture cases / 60 policy checks, development-v2 plan verification and dependency consistency passed. A browser rehearsal of the exported mock-mode launcher verified separate confirmation, matching/missing/excluded paths and explicit independent canned merchant status; Ctrl+C exited normally. No new test or runtime source changes were needed.

PR #21 remains open with changes requested; successful bounded review/status checks do not resolve merchant/refund review findings. CI keeps its prior resolution pin. No provider credentials, live AI/payment calls or other-lane/shared-file edits occurred. Human reference review/adjudication, measured completion effort, independently reviewed new holdout inputs with a supported reporting path, and a jointly recorded demo remain pending. See [COMPLETION.md](COMPLETION.md) and [HUMAN-EVALUATION.md](HUMAN-EVALUATION.md). Historical entries below retain their original date/scope.

---

# 8 November 2026: reserve evaluation reports before calls

Started `work/rajiv-eval-output` from merged main `e55f431` after verifying PR #19 merged with passing checks. Offline regressions reproduced unplanned report overwrite (including a symlink target), calls completing before an invalid parent path failed, and two competing CLI runs reaching extraction for one output. The key/preflight reservation check also failed against the unchanged evaluator. All reproduction used temporary synthetic files and patched adapters, not a provider account or historical report.

Both planned and unplanned commands now create required parents and exclusively open the final report path before reading a key or extracting. Existing files/directories/symlinks and invalid parents fail before those actions. The reservation remains open through evaluation/report writing and closes on success, credential failure or write/close error; a competing run cannot claim the same existing output path. Normal unavailable/mismatch results are still saved with their original CLI failure semantics. Later I/O errors are sanitized, exit nonzero, warn that calls may have occurred and do not cause an automatic retry.

A credential error after reservation leaves an empty closed file, not a result. Interruption or later write/close failure can also leave incomplete output; this is path preflight/overwrite protection, not atomic writing, journaling, crash recovery, immutable filesystem integrity or upstream cancellation. Use a fresh path for any new attempt. Programmatic `evaluate()` remains in-memory; no report schema, prompt, generation configuration or scoring rule changes.

The evaluator source hash intentionally changed. Preserved `development-v1.json` unchanged and created/verified `development-v2.json` offline for the same twelve authored development cases and explicit vision route. The new plan is setup evidence only, with holdout/human validation false, and is not retroactively attached to historical provider runs. Fixture/reference bytes and provider reports remain untouched.

Local verification on Python 3.11.16: 130 evidence tests passed with ResourceWarnings treated as errors and actual-service integration enabled, including seven new output-path/competing-run/cleanup regressions. Seven Node UI tests, three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, new development-v2 plan verification, dependency consistency and whitespace checks passed. The unchanged v1 plan correctly rejected the new evaluator source. Existing pinned dependencies were reused; no provider credentials, live AI/payment calls, fresh dependency install or new browser check were used. Hosted CI is reported separately.

Only evidence evaluation/tests/plans and Rajiv documentation change. Human reference review, adjudication, a supported separately reviewed holdout, completion-effort measurement and the jointly recorded demo remain pending. Git records commit/publication status.

---

# 8 November 2026: offline reference-review packet

Started `work/rajiv-label-review` from merged main `c80da2e` after verifying PR #18 merged with passing checks. Added an offline exporter for the existing twelve synthetic development images and a strict self-reported record checker. The standalone page embeds hash-checked pixels, uses opaque sample IDs and blank transcription/readability controls, and omits authored answers/mock proposals/provider output from form data. Image text can reveal fixture names; it is explicitly not a blinded study or holdout.

A person supplies a name/alias, independently reads each image, chooses readable/missing/unreadable/conflicting for both fields and explicitly checks the declaration before a local JSON download. Changing away from readable clears stale values. The checker verifies full coverage, manifest/image/packet identity, UTC timestamp shape, declaration and value/readability consistency, then preserves disagreements against authored typed-entry values. It never rewrites references or changes validation flags. Complete disagreements produce a report and exit 1; malformed/drifted input or existing output fails with exit 2. Identity, visual work and timestamps remain self-reported, not authenticated.

A blank local packet was exported under ignored `evidence/.local/label-review-development-v2/`. An actual browser check verified initially blank/disabled fields, readable-field enabling, clearing a temporary `AUTOMATED-UI-TEST` value on uncertainty, and resetting all controls to blank. The reviewer declaration remains unchecked and no completed human record was generated. Unit-test records and DOM-double exports are explicitly synthetic tooling checks, not review results. The page uses embedded data images and a no-network content policy; the local preview serves only that packet directory on loopback.

Local verification on Python 3.11.16: all 123 evidence tests passed with ResourceWarnings treated as errors and actual-service checks enabled, including nine new offline review tests. Seven Node UI tests (three new), three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, committed development-plan verification, dependency consistency, workflow YAML parsing and whitespace checks passed. Existing pinned dependencies were reused. Hosted checks are reported separately; no fresh install, live-provider run or human review is claimed.

Existing plans, authored fixture bytes/references and provider reports are unchanged. This makes reference auditing practical; independent labels, adjudication, a future supported holdout protocol and human effort measurement remain pending. See [LABEL-REVIEW.md](LABEL-REVIEW.md) for commands, sharing/privacy limits, checker semantics and the actual human step. Only evidence evaluation/tests/CI and Rajiv documentation change. Git records commit/publication status.

---

# 8 November 2026: customer demo rehearsal

Started `work/rajiv-demo-rehearsal` from merged main `4114744` after verifying PR #17 merged with passing checks. Added `python -m evidence.demo`: a one-command, loopback-only customer rehearsal using explicit mock fixture extraction, the unchanged committed resolution mock and an initially empty temporary evidence database. A supplied loopback resolution URL selects only an externally owned status dependency; the launcher does not create a merchant case or stop that external service. Owned servers and temporary storage are cleaned up on normal context exit or Ctrl+C.

Four new tests cover fresh/repeated starts, explicit mock configuration despite inherited provider/resolution environment, sample/assessment/status paths, storage and server cleanup, external-service lifetime, partial-startup failure cleanup and invalid origins/ports. The status UI now describes mock mode as simulated resolution rather than assuming every mock response is canned; actual resolution mock-mode reviews can be persisted records. The separate-record warning remains visible.

An actual in-app browser walkthrough using the launcher verified a matching manual assessment after separate confirmation, blank-batch clarification, an excluded batch with no safety claim, and explicitly simulated merchant status. The rehearsal process then exited cleanly via Ctrl+C. No live provider or payment was used. The 75-second script in [DEMO.md](DEMO.md) is a timed recording outline, not a measured recording or human-completion result.

Local verification on Python 3.11.16: 114 evidence tests passed with ResourceWarnings treated as errors and actual-service checks enabled, including four new launcher checks. Four Node UI tests, three shared-contract tests, the unchanged one-test resolution starter suite, 12 fixture cases / 60 policy checks, frozen development-plan verification, dependency consistency, JavaScript syntax and whitespace checks also passed. Existing pinned dependencies were reused; this is not a fresh network install or a new provider evaluation. Hosted checks are reported separately.

Only evidence code/tests/UI/docs and Rajiv documentation change. Resolution code, frozen contracts/mocks, root dependencies and provider reports remain untouched. Merchant UI, approval/reconciliation correctness (including the previously reproduced state regression), PayPal sandbox integration, a joint recorded demo, independently reviewed labels and human effort measurement remain pending. Git records commit and publication status.

---

# 8 November 2026: actual resolution review/status integration

Started `work/rajiv-resolution-smoke` from merged main `171b5ea` after verifying PR #16 merged and its evidence/shared-contract checks passed. Remote inspection found new resolution commit `e1e16be6928afcdd52015097a3bbab6b42ddbd8b`, with no resolution PR when checked. The earlier scaffold-only integration limitation no longer describes that branch.

Added six evidence-owned opt-in HTTP integration tests. The actual resolution server and actual merchant evidence client run in isolated subprocesses from an export of that exact source, with no inherited provider keys. Evidence and resolution own separate temporary SQLite databases; the test coordinator accesses only HTTP, explicitly handing off a synthetic assessment/order/remedy snapshot. A payment-denying adapter records any refund attempt and fails the check if invoked. Evidence CI checks out the same pinned commit separately and enables the optional checks; ordinary local runs explicitly skip them without a selected snapshot.

Observed behavior: an unknown case stays 404 until explicitly reviewed; eligible identifiers still need merchant remedy confirmation; missing and excluded identifiers stay unresolved/excluded; remaining minor units and old orders reach the expected review states; mismatched cases are rejected; repeated review/status reads preserve evidence; resolution retains the supplied assessment snapshot after a new evidence assessment; stopping resolution yields a visible customer 503 while typed entry remains usable. Review responses stay mock mode with null operation/refund IDs and no adapter attempts. No application implementation change was needed for these paths.

Local verification on Python 3.11.16: all 110 evidence tests passed with ResourceWarnings treated as errors, including all six actual-service checks enabled against the pinned export. The four Node UI tests, three shared-contract tests, unchanged one-test resolution starter suite, 12-case / 60-check fixture replay, committed development-plan verification, dependency consistency, JavaScript syntax and whitespace checks also passed. Existing pinned dependencies were reused; no fresh install, hosted CI run, browser recheck, live-provider evaluation or human study is claimed.

This establishes bounded synthetic compatibility of the review/status HTTP paths, not full integration or payment behavior. The handoff is supplied by the test coordinator, not a new product workflow. A retained assessment is not proof of freshness or authorization. Approval/refund execution, merchant UI, jointly reviewed integration, recorded demo, independently reviewed holdout labels and human measurement remain pending. No resolution source, shared contract, mock, root dependency or historical provider report was edited. No provider credentials or live AI/payment calls were used. Reproduction and exact scope: [integration runbook](INTEGRATION.md). Git records publication status.

---

# 7 November 2026: frozen evaluation-plan continuation

Started `work/rajiv-eval-freeze` from merged main `a445754` after verifying PR #15 merged with evidence/shared-contract CI passing. The resolution branch remains the original scaffold; actual merchant integration remains pending.

Added an offline development-evaluation plan and replay preflight. The selected input bytes and the entire authored-reference manifest are hashed; duplicate IDs/hashes, malformed references, repeated/unknown selectors, path escapes/symlinks, invalid images and typed decisions inconsistent with deterministic rules fail before extraction. Planned replay also checks model/timeout/URL, source/schema/lock hashes and Python/Pillow/jsonschema versions before reading credentials. Reports carry the plan fingerprint and checked snapshot. An offline `--check` verifies a plan without credential access; plans and planned reports refuse to overwrite existing files.

Twelve new offline tests cover plan creation/checking/replay, drift in references/pixels/code/runtime/configuration/selection, malformed/edited plans, false review flags, and preflight before key reads or report overwrites. Existing gateway/evaluation tests still pass. The committed twelve-case plan is a development setup record only; no provider result is generated, no prior report is rewritten, and holdout/human validation remain false. The fingerprint does not authenticate reviewers, prove an unseen dataset or pin the remote backend. Human-reviewed holdout labels and human completion/effort measurement remain pending.

Local verification on Python 3.11.16: 104 evidence tests with ResourceWarnings treated as errors (including 12 new offline evaluation-plan tests), 4 Node UI tests, 3 shared-contract tests, the unchanged resolution starter test, and 12 fixture cases / 60 policy checks passed. The committed development plan was created and verified offline. Dependency consistency, JavaScript syntax and whitespace checks passed. Existing pinned dependencies were reused; no fresh install, browser recheck, live-provider run or human study is claimed. Hosted CI is reported separately from these pre-commit local checks.

See [the evaluation runbook](EVALUATION.md). No live provider/payment calls or credentials were used; only evidence evaluation/tests/docs and Rajiv documentation change. No shared contract or resolution file is edited. Git records the commit and publication status.

---

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
