# Rajiv's evidence lane — fixture and opt-in OmniRoute extraction

Runnable synthetic customer flow with **mock fixture proposals or opt-in OmniRoute image proposals**, **manual confirmed-text assessment**, SQLite assessment history and a read-only resolution HTTP client. Default mode remains mock. Customer authentication, merchant handoff, payment execution and deployment are not implemented.

All code, runtime dependencies, storage and UI belong to `evidence/`. The frozen `contracts/` and committed resolution mock are read without changes. No imports from `resolution/` and no shared database.

## Run locally

From the repository root, Python 3.11+:

```sh
python3 -m venv evidence/.venv
evidence/.venv/bin/python -m pip install -r evidence/requirements.lock.txt
evidence/.venv/bin/python -m evidence.backend.server
```

Open http://127.0.0.1:8101. If the scaffold evidence mock already uses 8101, stop it or add `--port 8111` to the new server command. The evidence server deliberately binds loopback only.

In a second terminal, optionally start the **unchanged committed mock**:

```sh
python3 scripts/mock_server.py resolution --port 8102
```

`RESOLUTION_BASE_URL` configures the resolution origin (default `http://127.0.0.1:8102`). No credentials are required. A missing resolution service produces a visible unavailable status; it does not block label assessment or fabricate a success.

## Opt-in OmniRoute setup

The existing local gateway must be running on loopback, and its key must have payload logging disabled (`no_log`). The process environment's `OMNIROUTE_API_KEY` takes precedence; otherwise, supply an existing env file explicitly. Only that key is read; no file is sourced and no key is copied into this repository.

```sh
evidence/.venv/bin/python -B -m evidence.backend.server --extractor omniroute --omniroute-env /absolute/path/to/existing/.env --model gemini/gemini-3.1-flash-lite
```

The IIT KGP setup uses the same key name and `localhost:20128/v1`, with `auto/smart` for text routing. RecallRelay accepts that route as its default model argument, but the observed image run used the explicit vision route shown above. Early auto-route calls failed; no fallback success was fabricated. Successful proposals record the actual served model. Gateway package observed locally: 3.8.49. A served model tag is not an immutable backend revision.

The UI offers **Read label with AI** only in configured AI mode. The image is submitted only when selected; review and confirmation remain separate from extraction. A configured health result does not establish upstream availability. Calls have a supervised 20-second wait, a 64 KiB response cap, no client retries, and a two-call concurrency limit. A failed or truncated call leaves typed entry available.

## Try the customer flow

1. Choose **Clear label** and select **Use sample**. Review the canned values, check the confirmation box and check the campaign match.
2. Choose **Unreadable batch** and select **Use sample**. Confirm while leaving batch blank: the result stays `needs_information` and asks only for the batch. Enter `B101`, confirm again and reassess.
3. Use **Excluded batch** (`B103`): excluded from this campaign, with no product safety claim.
4. Upload an image from `evidence/evals/fixtures/` and select **Suggest from fixture image (mock)**. In default mock mode, only exact fixture bytes are recognized; low-confidence/conflicting fields remain blank. Uploaded pixels are **not read by a model or OCR in mock mode**, and filenames never determine suggestions. Opt-in AI mode sends pixels through OmniRoute instead.
5. Read the demo case status. The resolution mock reports a separate canned merchant record, not an automatic handoff from the current assessment. No money moves.

Editing identifiers invalidates the displayed result and clears confirmation. Missing values, `?` and common uncertainty markers cannot become eligible. Matching is case-sensitive with outer whitespace trimmed; exact approved model and batch membership is required, and an explicit excluded batch wins.

## API and storage

- `POST /v1/assessments`: frozen internal server-to-server request and response. Treat campaign/order snapshots as trusted internal inputs. The current service has no service authentication and must not accept real data.
- `GET /v1/assessments/{case_id}`: latest persisted assessment, no dependency callbacks.
- `/demo/assessments`: browser accepts only a label. Campaign/order come from the synthetic fixture held by the server.
- `/demo/extraction`: allowlisted canned sample ID, `mode: mock`, no persistence.
- `/demo/image-extraction`: bounded, decoded image → provider-neutral interface → configured fixture lookup or OmniRoute adapter. Unknown fixture images, provider failures or malformed outputs produce visible 503 errors, without an assessment or silent fallback. Suggestions must be confirmed separately.
- `/demo/resolution-status`: read-only GET for the server-held synthetic case. Strict schema and case-ID validation, bounded response, timeout, no redirects, visible 404/503 failures.
- `/health`: reports manual assessment and the configured extraction mode/provider separately, without probing the gateway.

Each assessment has a new ID when confirmed data changes. History is retained, exact repeats of the latest request reuse its saved response, and GET survives restart. A case cannot change campaign identity or order snapshot. Older campaign versions and changed rules at the same version return 409; a higher campaign version may be reassessed. These local behaviors are not an exactly-once guarantee.

Default storage: `evidence/.local/assessments.sqlite3` (ignored), override with `--db PATH`. Stored records contain campaign/order snapshots, confirmed evidence, assessment responses and a request digest. Image bodies are transient and are not stored or logged. Requests are capped at 3 MiB; images at 2 MiB, 4096 pixels per edge and 8 million pixels total. MIME must match a decodable, single-frame PNG/JPEG. Integrity verification is followed by pixel decoding; truncated, corrupt, animated or oversized images are rejected. These checks do not establish authenticity, safety or malware-free content. Duplicate JSON keys, non-finite constants and ambiguous request lengths are rejected.

The demo has no cross-origin write support and restricts Host to loopback names. These guards do not replace authentication or upload authorization. No public serving or real customer data.

## Verify

```sh
evidence/.venv/bin/python -B -m unittest discover -s evidence/tests -v
evidence/.venv/bin/python -B -m evidence.evals.run --check
node --check evidence/web/app.js
git diff --check
```

Direct runtime requirements live in `evidence/requirements.txt`; the tested transitive pins live in `evidence/requirements.lock.txt`. Evidence CI installs the lock and runs lane tests plus the fixture-policy replay. See [Rajiv's runbook](../docs/rajiv/RUNBOOK.md) for observed checks and remaining work. Passing these synthetic checks does not measure extraction accuracy, customer savings, live integration or payment behavior.

The fixture dataset has 12 fictional label variants. Its 60 replay checks validate adapter/uncertainty/confirmation plumbing and the authored typed-entry baseline, not image recognition or human completion. See [evaluation scope](evals/README.md) and [critical review](../docs/rajiv/REVIEW.md).

## Observed provider development check

The final 6 November 2026 run produced 12 proposals / 12 synthetic development cases, with 24/24 fields matching authored typed-entry references and zero unavailable calls in that run. Earlier failed runs remain in the reports. This is a previously visible development set, not a reviewed holdout, human completion study, calibrated confidence result, or general accuracy claim. See [provider evaluation](evals/reports/omniroute-development.json) and [evaluation limits](evals/README.md).
