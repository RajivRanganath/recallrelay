# Development guide

For contributors. Judges and first-time readers should start with the [README](../README.md).

## Two services, one contract

RecallRelay is one project made of two services joined by a fixed HTTP contract. Neither service imports the other's code or opens its database, so each can be run, tested and replaced on its own.

| Service | Side | AI | Backend | UI |
|---|---|---|---|---|
| `evidence/` | Customer evidence and eligibility | Label extraction and targeted clarification | Evidence storage, campaign rule checks, assessment API, unified workspace gateway | Label upload, confirmation and status; the unified workspace |
| `resolution/` | Merchant decision and settlement | Evidence-grounded case briefs | Case lifecycle, approval, PayPal refund adapter, webhook receiver | Merchant review, approval and refund status |

Built by [Rajiv](https://github.com/RajivRanganath) and [Vismaya](https://github.com/VismayaM2005).

- API contract, schemas and fixtures: [contracts/](../contracts/README.md)
- Customer side: [evidence/README.md](../evidence/README.md), [runbook](evidence/RUNBOOK.md)
- Merchant side: [resolution/README.md](../resolution/README.md), [runbook](resolution/RUNBOOK.md)

## Run the tests

From the repository root, after installing `evidence/requirements.lock.txt` into `evidence/.venv`:

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s tests -v
RECALLRELAY_RESOLUTION_SOURCE="$PWD" evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -v
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s resolution/tests -v
node --test evidence/tests/test_web.js evidence/tests/test_label_review_web.js evidence/tests/test_workspace_web.js
```

On Windows, use `.\evidence\.venv\Scripts\python.exe` and set `$env:RECALLRELAY_RESOLUTION_SOURCE = (Get-Location).Path` before the evidence suite. Tests use synthetic fixtures, local stubs and fake or disabled payments; none needs an account.

## Contract mocks

Each service can be developed against a mock of the other. Python 3.11 is enough; no keys.

```sh
python3 scripts/mock_server.py evidence --port 8101
python3 scripts/mock_server.py resolution --port 8102
```

```sh
curl -s http://127.0.0.1:8101/health
curl -s -X POST http://127.0.0.1:8101/v1/assessments -H 'Content-Type: application/json' --data-binary @contracts/fixtures/assessment-request.json
curl -s -X POST http://127.0.0.1:8102/v1/resolutions -H 'Content-Type: application/json' --data-binary @contracts/fixtures/resolution-request.json
```

Use `X-Mock-Scenario: missing` or `excluded` for evidence; `manual`, `pending` or `failed` for resolution. These headers exist only on the mocks. Responses carry `X-RecallRelay-Mode: mock`.

## Development history

Dated records are kept as written, including failures and corrections.

- Integration, merchant hardening and Windows maintenance: [PR #35](https://github.com/RajivRanganath/recallrelay/pull/35), [PR #36](https://github.com/RajivRanganath/recallrelay/pull/36)
- Unified workspace: [PR #39](https://github.com/RajivRanganath/recallrelay/pull/39), [PR #40](https://github.com/RajivRanganath/recallrelay/pull/40), [guide](evidence/UNIFIED-WORKSPACE.md)
- Evaluation method and protocol: [method](evidence/EVALUATION.md), [human protocol](evidence/HUMAN-EVALUATION.md), [timing provenance](evidence/LIVE-AI-TIMING.md)
- Merchant-side records: [resolution/](resolution/)
- Webhook approval boundary: [WEBHOOK-VERIFICATION.md](WEBHOOK-VERIFICATION.md)
