# Rajiv's evidence lane — reviewed mock-first extraction slice

Runnable synthetic customer flow with **provider-neutral extraction interfaces and mock fixture proposals**, **manual confirmed-text assessment**, SQLite assessment history and a read-only resolution HTTP client. No AI provider, customer authentication, merchant handoff, payment execution or deployment is implemented.

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

## Try the customer flow

1. Choose **Clear label** and select **Use sample**. Review the canned values, check the confirmation box and check the campaign match.
2. Choose **Unreadable batch** and select **Use sample**. Confirm while leaving batch blank: the result stays `needs_information` and asks only for the batch. Enter `B101`, confirm again and reassess.
3. Use **Excluded batch** (`B103`): excluded from this campaign, with no product safety claim.
4. Upload an image from `evidence/evals/fixtures/` and select **Suggest from fixture image (mock)**. Only exact fixture bytes are recognized; low-confidence/conflicting fields remain blank. Other synthetic PNG/JPEG photos can still use typed entry. Uploaded pixels are **not read by a model or OCR**, and filenames never determine suggestions.
5. Read the demo case status. The resolution mock reports a separate canned merchant record, not an automatic handoff from the current assessment. No money moves.

Editing identifiers invalidates the displayed result and clears confirmation. Missing values, `?` and common uncertainty markers cannot become eligible. Matching is case-sensitive with outer whitespace trimmed; exact approved model and batch membership is required, and an explicit excluded batch wins.

## API and storage

- `POST /v1/assessments`: frozen internal server-to-server request and response. Treat campaign/order snapshots as trusted internal inputs. The current service has no service authentication and must not accept real data.
- `GET /v1/assessments/{case_id}`: latest persisted assessment, no dependency callbacks.
- `/demo/assessments`: browser accepts only a label. Campaign/order come from the synthetic fixture held by the server.
- `/demo/extraction`: allowlisted canned sample ID, `mode: mock`, no persistence.
- `/demo/image-extraction`: bounded, decoded image → provider-neutral interface → exact fixture lookup. `mode: mock`; unknown images or malformed adapter outputs produce visible 503 errors, without an assessment or silent fallback. Suggestions must be confirmed separately.
- `/demo/resolution-status`: read-only GET for the server-held synthetic case. Strict schema and case-ID validation, bounded response, timeout, no redirects, visible 404/503 failures.
- `/health`: reports manual assessment and mock extraction separately.

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
