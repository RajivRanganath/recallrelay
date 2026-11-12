# Synthetic label fixtures and policy replay

Twelve fictional label variants live in `fixtures/`: clear PNG/JPEG, excluded and unknown batches, another model, missing identifiers, blur, crop, conflicting batches, an instruction-bearing note and a deliberately low-confidence proposal. Images are generated from authored text with Pillow; they are not customer photos, real recall labels or human annotations. Source text and expected visible/typed fields are recorded separately for blurred/cropped/conflicting cases.

The frozen manifest records version, image hashes, source text, typed-entry inputs, expected decisions, safe suggestions and authored mock provider outputs. Regeneration is an explicit command; evaluation rejects changed image bytes. Do not overwrite reviewed v1 fixtures casually. The render generator is not an OCR model.

From the repository root, after installing `evidence/requirements.lock.txt`:

```sh
evidence/.venv/bin/python -B -m evidence.evals.run --check
evidence/.venv/bin/python -B -m evidence.evals.run --check --output evidence/evals/reports/fixture-policy.json
```

This produces **12 cases / 60 checks** across field filtering, clarification, unconfirmed abstention, deterministic assessment after simulated confirmation and the authored typed-entry path. The checked-in report records the actual local runtime and failures. The fixture adapter looks up known image hashes and returns manifest-authored output. Passing this replay is policy/plumbing evidence only: **no image recognition, extraction accuracy, calibrated confidence, user-completion study or user-savings measurement**. Neither the typed inputs nor simulated confirmation measure human behavior. Instruction-bearing image replay does not test a real model's injection resistance.

To deliberately rebuild a fresh candidate dataset for review (not during evaluation):

```sh
evidence/.venv/bin/python -B -m evidence.evals.build_fixtures --output evidence/.local/candidate-fixtures
```

## Opt-in provider development smoke

`live.py` calls OmniRoute on the frozen images. It validates all selected hashes before any call, never uses `mock_output` as model output, and compares normalized proposals with the authored `typed_entry` reference. Those references describe visibility conservatively; they are not human annotations. The fixture-only low-confidence expectation is not reused as a live-model target.

```sh
evidence/.venv/bin/python -B -m evidence.evals.live --omniroute-env /absolute/path/to/existing/.env --model gemini/gemini-3.1-flash-lite --output evidence/.local/provider-development.json
```

Use repeated `--case CASE_ID` to limit calls. Calls use the configured provider account and may consume quota. A report includes every attempted case, unavailable calls and sanitized failure codes, per-field comparisons, guessed reference-missing fields, and simulated-confirmation decisions. Failed calls stay in the attempt denominator and contribute no fabricated field comparisons. The CLI writes the complete report, then exits nonzero for any unavailable call, field mismatch, or false eligible decision against authored references. This includes wrong fields that do not change eligibility and conservative abstentions where the authored reference contains a value. Inspect the rows to distinguish those outcomes; exit status alone is not an accuracy or safety measurement.

Observed 6 November reports:
- `omniroute-smoke-initial.json`: auto/smart, 512-token request, 0/3 usable proposals.
- `omniroute-smoke-vision.json`: explicit gemini/gemini-3.1-flash-lite, 2048 tokens, prompt label-image-1, 2/3 usable proposals; one invalid response remained.
- `omniroute-development.json`: explicit route, 2048 tokens, prompt label-image-2, 12/12 usable proposals, 24/24 fields matching authored typed-entry references, zero false eligible simulated outcomes against those references. The served model tag was gemini-3.1-flash-lite. Confidence remains uncalibrated.

A separate diagnostic observed auto-route HTTP 429, and HTTP 200 responses with finish_reason length were rejected during generation tuning. No request/response bodies or images are included in these reports. Gateway payload logging is a separate setting: it was enabled initially, then disabled for the reused key; this session's five earlier payload artifacts were removed while keeping status summaries.

These are development results after inspecting failures and tuning the request. They are not holdout accuracy, a robust prompt-injection result, or human approval/completion evidence. One instruction-bearing synthetic label and one conflicting label are included; this does not generalize to arbitrary attacks. Simulated confirmation is analysis only, with no persistence, merchant handoff, or payment.

Next: freeze a separately reviewed holdout, record actual served model/configuration and unknown backend revision, and evaluate field errors, clarification, and unsafe simulated eligibility against typed entry with every denominator and failure visible. Human review and a real completion study remain pending.

## Frozen development evaluations

Create an offline plan and verify it without credentials:

```sh
evidence/.venv/bin/python -B -m evidence.evals.plan --model gemini/gemini-3.1-flash-lite --output evidence/.local/development-plan.json
evidence/.venv/bin/python -B -m evidence.evals.plan --check evidence/.local/development-plan.json
```

The plan fingerprints selected images, the entire manifest including references, relevant source/schemas/lock file, model/URL/timeout and Python/Pillow/jsonschema versions. Preflight rejects duplicate cases/hashes, malformed references and typed decisions inconsistent with the deterministic rules before a provider call. `live.py --plan PATH` verifies the setup before reading credentials, defaults to the frozen model/timeout/cases, and records the plan fingerprint and checked snapshot in its report. Both planned and unplanned commands reserve a new report path before reading a key or extracting; existing files/directories/symlinks and unusable parents fail before calls. Neither mode overwrites historical reports. Pass the same `--manifest PATH` to freeze/check/replay a custom synthetic v1 dataset. Runs without a plan remain supported and record a snapshot with a null plan fingerprint.

The current committed `plans/development-v3.json` is an offline setup record for portable, symlink-safe report reservation. It binds the new reservation helper and the changed evaluator/plan source. The v1/v2 plans and their reports are preserved unchanged as historical evidence; their source fingerprints intentionally reject the newer code. V3 has no new provider or human result. Exact runtime/package checks can also intentionally reject a different platform environment; freeze a new named plan for that reviewed setup instead of rewriting historical plans. See [the evaluation runbook](../../docs/evidence/history/EVALUATION.md) for opt-in replay, what is checked, and human-review limits. Current plans and reports stay development-only, with holdout/human validation false.

## Offline reference-review packet

Prepare a new blank packet with `evidence/.venv/bin/python -B -m evidence.evals.review prepare --output evidence/.local/new-development-review`. A person reads the embedded synthetic images, records field values/readability and downloads a self-reported JSON record. `review check` verifies packet/dataset identity, complete coverage and field shape, then preserves disagreements against authored typed-entry references. It never rewrites labels or marks them human validated/holdout. No credentials or provider calls are involved. See [review instructions](../../docs/evidence/history/LABEL-REVIEW.md). These existing development images remain previously visible; the packet is not a new holdout or human-study result.

A failed credential read after output reservation leaves a closed empty file, not a result. Interrupted or later write/close failures can leave incomplete output and do not cancel accepted upstream work. Choose a fresh path for a new attempt; there is no automatic retry, atomic-write or crash-recovery claim. See the evaluation runbook for precise scope.

## Offline completion-effort summaries

`python -m evidence.evals.study_report --sessions PATH --trials PATH --output NEW_JSON` validates actual returned records using the exact blank templates in `study/`. It reports first attempts and retries separately, preserves unavailable/failed/timed-out/unrecorded tasks, and pairs completed first attempts only within one session/case. It recomputes authored-reference field/decision comparisons and leaves sessions/modes separate. Empty sheets produce `no_observations`; all human-validation/holdout flags remain false. No credentials or provider calls are used. See [the human-evaluation protocol](../../docs/evidence/history/HUMAN-EVALUATION.md) for exact session/trial conventions and the remaining human steps.

## Unseen label set

`unseen-2026-11-12/` holds twelve further fictional labels that the extraction prompt was not tuned against, built by `build_unseen.py` with references authored from the rendered images and frozen by hash before any model call. Run a provider on it with `evidence.evals.live --manifest evidence/evals/unseen-2026-11-12/manifest.json`. Results, including one invented reading and one timed-out call, are in [the evaluation results](../../docs/evidence/EVALUATION-RESULTS.md). Do not tune the prompt on these images.
