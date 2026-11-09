# Freeze and replay an evidence evaluation

Current results, 9 November 2026: the reference review, earlier mock pilot and separate completed actual-provider human pilot are recorded in [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md). That development pilot supplies observed completion effort; the frozen replay tool below still measures provider proposals separately. No holdout or general savings claim is supported. Older pending-work descriptions below retain the tools' original scope.

The current twelve fictional labels are a previously inspected development set. Their typed-entry references are authored, not independently human validated. The plan added here freezes that development setup; it does not turn it into a holdout or measure completion effort.

## Create and check a plan offline

These commands do not read a key, contact OmniRoute, consume provider quota or change the application extractor.

```sh
evidence/.venv/bin/python -B -m evidence.evals.plan --model gemini/gemini-3.1-flash-lite --output evidence/.local/new-development-plan.json
evidence/.venv/bin/python -B -m evidence.evals.plan --check evidence/.local/new-development-plan.json
```

The current committed example is `evidence/evals/plans/development-v2.json`. The original `development-v1.json` remains an unchanged historical setup record; its old evaluator hash intentionally fails against the updated source. Check it with the same interpreter and installed Pillow/jsonschema versions used to create it. A different runtime or code revision should fail verification; intentionally create a separately named plan for a new setup. Plan creation refuses to overwrite an existing file. Use repeated `--case CASE_ID` when freezing a subset; the plan stores the selected order from the manifest. `--manifest PATH` selects an alternative synthetic v1 manifest for both creation and checking.

Before freezing, preflight checks strict JSON, nonempty cases, unique IDs and image hashes, directory-contained nonsymlink image files, image integrity/MIME/size, reference field shape and each selected typed decision against the frozen campaign rules. Selected pixels are decoded and retained in memory for evaluation so the provider receives the checked bytes. Unknown/repeated selectors fail rather than silently changing the denominator. All selected cases are checked before any extraction call.

A plan records the raw manifest hash (including authored references), selected image hashes, provider/model/loopback URL/timeout, evaluator/prompt/normalizer/rules/schema source hashes, the dependency-lock hash, Python version and installed Pillow/jsonschema versions. Its fingerprint covers its contents. Fixed generation parameters and the prompt are bound through the adapter source hash; the report also records request configuration and actual served-model provenance when supplied by the adapter. The remote backend revision remains unknown.

## Replay only after the plan is checked

This command uses the existing provider account and can consume quota. It requires the previously documented local gateway and key payload-logging configuration. Nothing in this continuation has run it against a live provider.

```sh
evidence/.venv/bin/python -B -m evidence.evals.live --plan evidence/.local/new-development-plan.json --omniroute-env /absolute/path/to/existing/.env --output evidence/.local/new-development-report.json
```

The model, timeout and selected cases default to the frozen settings. For a custom dataset, supply the same `--manifest PATH`. Explicit overrides must match the plan. Drift fails before output reservation or credential reads. Both planned and unplanned commands create any missing parent directories and exclusively reserve a new report file before reading credentials or making extraction calls. Existing files, directories, existing-target symlinks and dangling symlinks are rejected without touching their contents. A competing CLI run cannot claim that same existing output path. Reports contain the checked snapshot, with a plan fingerprint for planned runs and null for unplanned runs.

If configuration loading fails after reservation, the closed file remains empty: it is not a completed report, and retrying requires a new output path. Interruption or later write/close failure can also leave an empty or incomplete file; the command makes no atomic-write, crash-recovery, incremental-journal or upstream-cancellation guarantee. Path reservation prevents predictable filesystem/path failures and accidental overwrite before calls, but does not guarantee later disk availability. Later I/O errors exit nonzero, warn that calls may have occurred, and never retry them automatically.

Reports retain unavailable calls in the attempt denominator, per-field comparisons, reference-missing guesses, clarification and simulated decisions. The CLI saves the complete report and fails unavailable calls, field mismatches or false eligibility. A plan does not change these scoring rules. Earlier checked-in provider reports remain historical and are not retroactively linked to this plan.

## Review and interpretation limits

Fingerprints detect drift against a supplied plan; they are not signatures or proof of when a plan was created, reviewer identity, an unseen dataset, an unchanged remote model, or absence of tuning. Verification checks local files and the recorded runtime at preflight, not continuous filesystem integrity. Identical setup does not promise identical model outputs. Installed transitive dependency versions are not fully attested by hashing the lock file.

Both plans and reports remain `holdout: false`, `human_validated: false`; confidence remains uncalibrated. False claims in an edited plan are rejected, even if its fingerprint is recomputed. New independently reviewed labels, a frozen review record and a supported holdout reporting protocol are separate pending work. Do not reuse these twelve development labels as an unseen test set. Human completion/time/savings measurement also remains pending; simulated confirmation is not human behavior.

## Local checks

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_eval_plan.py' -v
evidence/.venv/bin/python -B -m evidence.evals.plan --check evidence/evals/plans/development-v2.json
```

Tests use synthetic placeholders and patched adapter outputs, plus the existing authored loopback gateway tests. No provider account, payments, merchant integration, real customer data or human-study result is involved.

## Audit authored references offline

`evidence.evals.review prepare --output NEW_DIRECTORY` exports a blank standalone form with checked images and a packet fingerprint; `review check --packet PATH --review PATH --output NEW_REPORT` validates a returned self-reported record and retains disagreements. Neither command calls a provider or changes labels/plans/reports. All outputs stay development-only with holdout/human-validation false. The declaration must be completed by an actual reviewer, not an agent. See [the label-review instructions](LABEL-REVIEW.md) for exact commands, exit codes, limits and adjudication. This audits existing development references; a separately reviewed holdout and human timing study remain pending.

## Prospective human evaluation

[HUMAN-EVALUATION.md](HUMAN-EVALUATION.md) defines the reference adjudication handoff, a small repeated-case completion pilot and prerequisites for a future holdout. Blank CSVs live in `evidence/evals/study/`; they contain no results. The current commands still produce development-only records and do not claim to implement a validated holdout protocol.
