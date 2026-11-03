# RecallRelay

A two-person, sandbox-only recall-resolution prototype.

**Status: collaboration scaffold, contracts, fixtures and mock servers only.** There is no implemented AI, customer authentication, real assessment, payment execution, production UI or deployment yet. Mock responses are labeled `mock`; no money moves.

## Equal ownership

| Contributor | Complete feature | AI | Backend | UI |
|---|---|---|---|---|
| [Rajiv](https://github.com/RajivRanganath) | Customer evidence and eligibility | Label extraction and targeted clarification | Evidence storage, campaign rule checks, assessment API | Customer upload, confirmation and status flow |
| [Vismaya](https://github.com/VismayaM2005) | Merchant decision and settlement | Evidence-grounded case briefs and next-action explanations | Case lifecycle, approval and PayPal refund adapter | Merchant review, approval and refund status flow |

Both own tests, evaluation and documentation for their feature. Each lane has **20 relative effort points**, including integration and demo work. These are planning estimates, not promised hours. No person is the other's frontend or backend implementer.

## Start independently

Python 3.11+ is enough for the mock servers. No keys or accounts required.

```sh
git clone https://github.com/RajivRanganath/recallrelay.git
cd recallrelay
python3 scripts/mock_server.py evidence --port 8101
```

In a second terminal:

```sh
python3 scripts/mock_server.py resolution --port 8102
```

- Rajiv: [start here](docs/START-RAJIV.md), branch `work/rajiv-evidence`.
- Vismaya: [start here](docs/START-VISMAYA.md), branch `work/vismaya-resolution`.
- [Task split](docs/TASKS.md) · [API contract](contracts/README.md) · [Ownership](AGENTS.md) · [Scope](docs/SCOPE.md)

Try the fixtures (mock responses echo scenario data, not AI or live decisions):

```sh
curl -s http://127.0.0.1:8101/health
curl -s -X POST http://127.0.0.1:8101/v1/assessments -H 'Content-Type: application/json' --data-binary @contracts/fixtures/assessment-request.json
curl -s -X POST http://127.0.0.1:8102/v1/resolutions -H 'Content-Type: application/json' --data-binary @contracts/fixtures/resolution-request.json
```

Use `X-Mock-Scenario: missing` or `excluded` for evidence; `manual`, `pending`, or `failed` for resolution. These are mock-only headers, not production API inputs. Inspect response headers for `X-RecallRelay-Mode: mock`.

## Verify setup

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m unittest discover -s evidence/tests -v
python -m unittest discover -s resolution/tests -v
```

The shared tests check fixture schemas, fixed port mocks and invalid mock input. Lane tests currently verify their example contracts; replace/extend them with behavior tests as implementation lands. Passing scaffold checks does not validate AI or payment correctness.

## Product boundary

One fictional US-selling brand, one approved refund campaign, USD, original PayPal captures within the supported refund window. Older or ambiguous cases stay unresolved. A label image is not proof of authenticity, ownership, disposal or safety. No claim of fraud detection or guaranteed recall compliance.

This repository starts private. Making it public, deploying it or entering a hackathon is a separate action. Secrets and customer data must never be committed.
