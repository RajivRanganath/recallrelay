# RecallRelay

A two-person, sandbox-only recall-resolution prototype.

**Status: implemented local synthetic prototype.** The customer and merchant apps are connected through HTTP: confirmed label assessment → merchant review and approval → refund result → customer status. AI adapters and a PayPal sandbox adapter are implemented with limited recorded evaluations. The integrated launcher uses mock extraction, template briefs and fake payments by default. Authentication, real customer use, live-money payments and public deployment are outside this prototype.

## Run both apps

From the repository root, on macOS/Linux with Python 3.11:

```sh
python3 -m venv evidence/.venv
evidence/.venv/bin/python -m pip install -r evidence/requirements.lock.txt
evidence/.venv/bin/python -B -m evidence.integrated --port 0 --merchant-port 0
```

Windows PowerShell:

```powershell
py -3.11 -m venv evidence/.venv
.\evidence\.venv\Scripts\python.exe -m pip install -r evidence/requirements.lock.txt
.\evidence\.venv\Scripts\python.exe -B -m evidence.integrated --port 0 --merchant-port 0
```

Open the printed customer and merchant URLs. Check and confirm a synthetic label, assess it, then choose **Send for merchant review**. In the merchant app select the same case, review it and confirm remedy conditions before approving the exact fake refund amount. Return to the customer app to read its status. The merchant's **Load demo case** button is a separate fixture seeder and is not the customer handoff.

Both services use separate temporary databases. Ctrl+C stops them and removes rehearsal state; restarting creates a fresh session. Port `0` chooses unused ports without terminating other listeners. Reuse an existing lane environment if already installed.

[Full integration instructions and limits](docs/rajiv/FINAL-INTEGRATION.md) · [Verification record](docs/rajiv/FINAL-INTEGRATION-CHECKS.md)

## Equal ownership

| Contributor | Complete feature | AI | Backend | UI |
|---|---|---|---|---|
| [Rajiv](https://github.com/RajivRanganath) | Customer evidence and eligibility | Label extraction and targeted clarification | Evidence storage, campaign rule checks, assessment API | Customer upload, confirmation and status flow |
| [Vismaya](https://github.com/VismayaM2005) | Merchant decision and settlement | Evidence-grounded case briefs and next-action explanations | Case lifecycle, approval and PayPal refund adapter | Merchant review, approval and refund status flow |

Both own tests, evaluation and documentation for their feature. Each lane has **20 relative effort points**, including integration and demo work. These are planning estimates, not promised hours. No person is the other's frontend or backend implementer.

## Original independent mock setup

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

## Verify the implementation

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s tests -v
RECALLRELAY_RESOLUTION_SOURCE="$PWD" evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -v
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s resolution/tests -v
node --test evidence/tests/test_web.js evidence/tests/test_label_review_web.js
```

On Windows, use `.\evidence\.venv\Scripts\python.exe` for the Python executable and set `$env:RECALLRELAY_RESOLUTION_SOURCE = (Get-Location).Path` before the evidence suite. Tests use synthetic fixtures, local stubs or fake/disabled payments. CI and the dated verification records identify the exact platform, commit and scope; passing these checks does not establish general AI accuracy, user savings or production readiness.

## Evidence and remaining acceptance

- Customer label review, mock pilot and separate real-provider human timing: [evaluation results](docs/rajiv/EVALUATION-RESULTS.md). These are familiar synthetic development inputs, not a validated holdout or causal time-saving study.
- Merchant model evaluation and real PayPal sandbox experiments: [resolution runbook](docs/vismaya/RUNBOOK.md). Historical provider runs are separate from the default fake-payment launcher.
- Integration, merchant hardening and Windows maintenance are merged through [PR #36](https://github.com/RajivRanganath/recallrelay/pull/36) and [PR #35](https://github.com/RajivRanganath/recallrelay/pull/35). Issues #1–#4 and #6–#9 are closed; [#5](https://github.com/RajivRanganath/recallrelay/issues/5) and [#10](https://github.com/RajivRanganath/recallrelay/issues/10) remain open for the deferred recording. [Combined recording outline](docs/rajiv/FINAL-DEMO.md).
- One real PayPal **sandbox** webhook recovery and replay exercise passed on 12 November 2026: one simulated 20.00 USD refund, two verified deliveries, matching provider read-back and customer status. The temporary registration was deleted and the tunnel stopped. [Measured results and limits](docs/WEBHOOK-RESULTS.md).
- Public access is disabled. A future external exercise requires a new scoped approval under the [prerequisites and approval boundary](docs/WEBHOOK-VERIFICATION.md). This single result does not establish production readiness or an exactly-once guarantee.

## Product boundary

One fictional US-selling brand, one approved refund campaign, USD, original PayPal captures within the supported refund window. Older or ambiguous cases stay unresolved. A label image is not proof of authenticity, ownership, disposal or safety. No claim of fraud detection or guaranteed recall compliance.

This repository starts private. Making it public, deploying it or entering a hackathon is a separate action. Secrets and customer data must never be committed.
