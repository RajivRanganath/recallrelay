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

Next: freeze a separately reviewed holdout set, capture genuine provider outputs with model/version/configuration, compare field errors, unsafe eligibility and clarification outcomes against typed entry on identical cases, and report every denominator/failure. Never evaluate a fixture lookup as if it were a model.
