# Development evaluation results — 9 November 2026

Task #4 now has a returned human reference review, historical provider comparison, an earlier human mock pilot, and a separate actual live-AI-versus-typed human pilot. Modes and runs remain separate. These are previously visible synthetic development cases with authored references, not a holdout or causal savings study. The results are ready for contributor acceptance in the evaluation PR.

## Actual live-AI human pilot

One internal participant completed all 24 first attempts: twelve typed tasks followed by twelve reverse-order AI-assisted tasks on identical image bytes. Every assisted task requested the actual provider once. All twelve requests returned usable proposals; no failures, timeouts, early stops, unavailable extractions, skipped suggestions or retries were recorded in this run. The earlier mock pilot's accidental stop/retry and skipped suggestion remain unchanged in their own results.

| Actual human condition | Completed / attempts | Median time | Range | Final identifier mismatches / compared fields |
|---|---:|---:|---:|---:|
| Typed entry | 12 / 12 | 8.0325 s | 3.079–11.911 s | 0 / 24 |
| Live AI assistance | 12 / 12 | 4.8825 s | 3.958–7.586 s | 0 / 24 |

All twelve first-attempt case pairs completed. Their median typed-minus-AI difference was 2.276 seconds, ranging from -3.040 to 6.937 seconds; two cases took longer with AI. No identifier edits after suggestions were recorded. Both arms ended with three eligible, four excluded and five needs_information decisions. There were zero observed false-eligible or rule-inconsistent final decisions against authored references. Five unresolved cases per arm remained unresolved; follow-up clarification resolution effort was not measured. Appropriateness judgments for those clarifications remain unknown, separate from deterministic rule agreement.

The live requests used OmniRoute, requested model gemini/gemini-3.1-flash-lite, served model gemini-3.1-flash-lite on all twelve responses, prompt label-image-2, temperature 0, max_tokens 2048, reasoning_effort none and a 20-second adapter deadline without client retries. All 24 normalized proposal fields agreed with authored references; simulated proposal checks found zero false eligibility. These proposal checks are separate from the participant's actual confirmed decisions. Returned model IDs do not attest an immutable remote backend.

The [actual AI machine-readable report](../../evidence/evals/reports/development-live-ai-human-pilot-2026-11-09.json) retains all 24 attempts, twelve provider outcomes/source records, paired times, errors, unresolved counts and hashes. Actual browser autosaved records were recovered from the loopback journal and preserved unchanged in content; this is explicitly distinguished from a located download. The importer checked each successful browser proposal against the normalized actual-provider record and checked frozen collector/source/image bindings. No identities, aliases, private notes, raw final identifiers, full images or secrets are published.

The participant had already reviewed and timed these images in the mock pilot. Fixed order, memory, repeated cases, preloaded images outside the timer and browser timing constrain interpretation. The observed times include the Read label with AI click, provider wait, review/confirmation and first assessment. They exclude file selection and follow-up resolution. An unscored typed practice is excluded. Identity, consent and timings remain unauthenticated; local binding checks do not establish independent human validation. No measured claim applies to a future automatic-on-upload flow. See [the collection handoff and provenance](LIVE-AI-TIMING.md).

## Reference review

One person returned the twelve-image packet and personally completed its declaration. The checker accepted 24 model/batch observations, with zero identifier-value disagreements against authored references. Label-001 was a guided example and its note is preserved. The images were previously visible development fixtures. Readability categories themselves have no authored scoring target. There were no identifier disagreements to adjudicate; no adjudication decisions were invented.

Original review, packet, audit and identifying notes remain local. The summary binds their hashes and retains human_validated: false, holdout: false and unauthenticated-identity limits. Agreement does not establish independence or general label correctness.

## Real-provider extraction versus authored typed references

The retained [6 November provider report](../../evidence/evals/reports/omniroute-development.json) attempted all twelve images through OmniRoute with gemini/gemini-3.1-flash-lite: 12 usable proposals, zero unavailable calls, 24 matching fields out of 24 comparisons and zero false-eligible simulated outcomes against authored typed references. Earlier failed runs remain in the reports directory.

Those inputs were inspected during tuning. This is development-reference agreement, not unseen accuracy, calibrated confidence, arbitrary injection resistance or a human AI-assisted completion study. No new provider calls were made for this closeout.

## Earlier human mock workflow pilot

One internal participant used the actual customer app. An unscored fictional practice was excluded. All twelve development images were attempted with typed entry, then assigned to mock assistance in reverse order. Images were preloaded outside the timer in both conditions. The browser monotonic timer ran from image reveal until the first visible assessment result. File selection was excluded. These changes from the moderator-stopwatch protocol are recorded.

The final first attempt ended through an accidental Stop click, as reported by the participant. Its original withdrawn outcome remains, with that explanation. A new attempt completed in 4.820 seconds. The retry is separate and never replaces the first attempt in medians.

| Recorded phase | Completed / attempts | Other outcome | Median completed time | Identifier mismatches / compared fields |
|---|---:|---|---:|---:|
| Typed first attempts | 12 / 12 | None | 8.744 s | 0 / 24 |
| Assigned mock first attempts | 11 / 12 | 1 accidental stop | 3.828 s | 0 / 22 |
| Assigned mock retry | 1 / 1 | None | 4.820 s | 0 / 2 |

All 24 distinct assigned tasks have a completed attempt across 25 retained records. There were no recorded request failures/timeouts and no observed false-eligible or rule-inconsistent completed decisions against development references. Five completed results per assigned arm remained needs_information. Completion means reaching the first assessment, not resolving missing information or completing a refund. Follow-up clarification effort was not measured.

The assigned mock trial for low-confidence was completed without requesting a suggestion. It remains in its assigned-arm summary with the deviation visible; it cannot be described as an observed suggestion-assisted completion. Twelve mock suggestion requests were recorded across original attempts and retry, with no recorded extraction unavailability.

Eleven first-attempt pairs completed; their median typed-minus-assigned-mock difference was 4.783 seconds. This includes the no-suggestion deviation. A marked exploratory subset has ten completed first-attempt pairs that actually requested suggestions. It excludes the accidental-stop pair and the no-request case, which remain in the full results. The machine-readable report records that subset separately. These descriptive differences do not demonstrate user savings.

## Limits and provenance

Human assistance was exact-byte mock fixture lookup with authored suggestions; no model or OCR ran during human timing. The live provider was measured separately in the historical extraction report. One participant, prior image review, a guided label, repeated cases, fixed typed-first order, reversed second-phase order, preloading and the retry constrain interpretation. Learning, memory and order are confounded. Identity, consent and timings are self-reported; hashes detect drift, not authenticity. No causal, population, live-AI workflow, payment or production claim follows.

The [machine-readable results](../../evidence/evals/reports/development-human-pilot-2026-11-09.json) retain every synthetic-case attempt, denominators, skipped request, accidental stop, retry, commits and input/instrumentation hashes. Aliases, private notes, raw final identifiers and assessment IDs are omitted. Original downloads, CSVs and frozen instrumentation remain under ignored local human-review-2026-11-09, human-pilot-2026-11-09 and human-pilot-retry-2026-11-09 directories inside evidence/.local/.

Offline checks validated the review, task/image schedule, download/source bindings, 25 retained attempts and CSV/report consistency. Separate calculations from raw timing rows matched outcome counts and condition medians. This closeout changes evaluation artifacts and Rajiv documentation only. Hosted CI is separate; no new runtime behavior, live provider run or holdout evaluation is claimed.
