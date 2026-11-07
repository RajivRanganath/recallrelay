# Freeze and replay an evidence evaluation

The current twelve fictional labels are a previously inspected development set. Their typed-entry references are authored, not independently human validated. The plan added here freezes that development setup; it does not turn it into a holdout or measure completion effort.

## Create and check a plan offline

These commands do not read a key, contact OmniRoute, consume provider quota or change the application extractor.

```sh
evidence/.venv/bin/python -B -m evidence.evals.plan --model gemini/gemini-3.1-flash-lite --output evidence/.local/new-development-plan.json
evidence/.venv/bin/python -B -m evidence.evals.plan --check evidence/.local/new-development-plan.json
```

The committed example is `evidence/evals/plans/development-v1.json`. Check it with the same interpreter and installed Pillow/jsonschema versions used to create it. A different runtime or code revision should fail verification; intentionally create a separately named plan for a new setup. Plan creation refuses to overwrite an existing file. Use repeated `--case CASE_ID` when freezing a subset; the plan stores the selected order from the manifest. `--manifest PATH` selects an alternative synthetic v1 manifest for both creation and checking.

Before freezing, preflight checks strict JSON, nonempty cases, unique IDs and image hashes, directory-contained nonsymlink image files, image integrity/MIME/size, reference field shape and each selected typed decision against the frozen campaign rules. Selected pixels are decoded and retained in memory for evaluation so the provider receives the checked bytes. Unknown/repeated selectors fail rather than silently changing the denominator. All selected cases are checked before any extraction call.

A plan records the raw manifest hash (including authored references), selected image hashes, provider/model/loopback URL/timeout, evaluator/prompt/normalizer/rules/schema source hashes, the dependency-lock hash, Python version and installed Pillow/jsonschema versions. Its fingerprint covers its contents. Fixed generation parameters and the prompt are bound through the adapter source hash; the report also records request configuration and actual served-model provenance when supplied by the adapter. The remote backend revision remains unknown.

## Replay only after the plan is checked

This command uses the existing provider account and can consume quota. It requires the previously documented local gateway and key payload-logging configuration. Nothing in this continuation has run it against a live provider.

```sh
evidence/.venv/bin/python -B -m evidence.evals.live --plan evidence/.local/new-development-plan.json --omniroute-env /absolute/path/to/existing/.env --output evidence/.local/new-development-report.json
```

The model, timeout and selected cases default to the frozen settings. For a custom dataset, supply the same `--manifest PATH`. Explicit overrides must match the plan. Drift and an already existing report path fail before reading credentials. Planned reports use exclusive creation and contain the plan fingerprint plus the checked snapshot. Legacy development runs without `--plan` remain supported and record an input snapshot with a null plan fingerprint.

Reports retain unavailable calls in the attempt denominator, per-field comparisons, reference-missing guesses, clarification and simulated decisions. The CLI saves the complete report and fails unavailable calls, field mismatches or false eligibility. A plan does not change these scoring rules. Earlier checked-in provider reports remain historical and are not retroactively linked to this plan.

## Review and interpretation limits

Fingerprints detect drift against a supplied plan; they are not signatures or proof of when a plan was created, reviewer identity, an unseen dataset, an unchanged remote model, or absence of tuning. Verification checks local files and the recorded runtime at preflight, not continuous filesystem integrity. Identical setup does not promise identical model outputs. Installed transitive dependency versions are not fully attested by hashing the lock file.

Both plans and reports remain `holdout: false`, `human_validated: false`; confidence remains uncalibrated. False claims in an edited plan are rejected, even if its fingerprint is recomputed. New independently reviewed labels, a frozen review record and a supported holdout reporting protocol are separate pending work. Do not reuse these twelve development labels as an unseen test set. Human completion/time/savings measurement also remains pending; simulated confirmation is not human behavior.

## Local checks

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_eval_plan.py' -v
evidence/.venv/bin/python -B -m evidence.evals.plan --check evidence/evals/plans/development-v1.json
```

Tests use synthetic placeholders and patched adapter outputs, plus the existing authored loopback gateway tests. No provider account, payments, merchant integration, real customer data or human-study result is involved.
