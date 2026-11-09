# Development evaluation results — 9 November 2026

This is a development-pilot checkpoint for task #4. Its synthetic evidence now includes the labeled set, historical real-provider field comparison, a returned human reference review, and a small human typed-versus-mock workflow pilot. The provider comparison and human timing pilot are separate measurements. No live-AI human completion-time result is supplied, so the AI-versus-typed effort criterion remains incomplete. See [the separate live-AI collection handoff](LIVE-AI-TIMING.md).

## Reference review

One person returned the twelve-image packet and personally completed its declaration. The checker accepted 24 model/batch observations, with zero identifier-value disagreements against authored references. Label-001 was a guided example and its note is preserved. The images were previously visible development fixtures. Readability categories themselves have no authored scoring target. There were no identifier disagreements to adjudicate; no adjudication decisions were invented.

Original review, packet, audit and identifying notes remain local. The summary binds their hashes and retains human_validated: false, holdout: false and unauthenticated-identity limits. Agreement does not establish independence or general label correctness.

## Real-provider extraction versus authored typed references

The retained [6 November provider report](../../evidence/evals/reports/omniroute-development.json) attempted all twelve images through OmniRoute with gemini/gemini-3.1-flash-lite: 12 usable proposals, zero unavailable calls, 24 matching fields out of 24 comparisons and zero false-eligible simulated outcomes against authored typed references. Earlier failed runs remain in the reports directory.

Those inputs were inspected during tuning. This is development-reference agreement, not unseen accuracy, calibrated confidence, arbitrary injection resistance or a human AI-assisted completion study. No new provider calls were made for this closeout.

## Human workflow pilot

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
