# Rajiv's evidence runbook

Date: 5 November 2026. Branch: `work/rajiv-evidence-intake`, started from `work/rajiv-evidence` and fast-forwarded to the existing main task-link documentation commit. Verification was completed locally before publication of the evidence feature branch. No deployment or live provider operation occurred.

## Run and demonstrate

Follow [evidence setup](../../evidence/README.md) using Python 3.11+ and `evidence/requirements.lock.txt`. No keys are needed. Start the evidence server on loopback; optionally start the unchanged committed resolution mock on 8102. Avoid port conflicts with the scaffold evidence mock.

First path: clear sample → confirm → manual campaign match; unreadable sample → needs information → correction → reconfirm; excluded sample → campaign-only exclusion; read merchant status → separately labeled canned mock. No refund authority or automatic merchant case creation.

Next-stage path: upload `evidence/evals/fixtures/conflicting-batches.png` → **Suggest from fixture image (mock)** → model suggestion, blank batch and one question → confirm while keeping batch blank → `needs_information`. Use a different valid synthetic image to see the explicit fixture-lookup failure, then type identifiers manually. The adapter recognizes exact fixture bytes only; no OCR is running.

Storage: ignored `evidence/.local/assessments.sqlite3`, override with `--db`. Records contain trusted campaign/order snapshots, confirmed fields, request digest and immutable assessment responses. Image bodies stay transient. Internal v1 is unauthenticated and trusts its caller; the browser endpoint holds synthetic campaign/order data server-side. Real data is out of scope.

## Verification

Current results and critical findings: [REVIEW.md](REVIEW.md). Latest observed local and source-export evidence suites: 57 tests passed on Python 3.11.16. Shared contract checks: 3 passed; unchanged resolution starter: 1 passed. Fixture-policy replay: 12 cases / 60 checks / zero failures, explicitly in mock mode. These results do not measure model accuracy, human behavior or payment correctness.

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -v
evidence/.venv/bin/python -B -m evidence.evals.run --check
node --check evidence/web/app.js
git diff --check
```

The preceding browser session also checked clear/uncertain/excluded typed paths, correction invalidation, upload preview, resolution unavailable/mock modes and narrow/desktop layout without horizontal overflow at observed CSS widths of 325 and 1066 pixels. The latest browser session verified the new conflict and unknown-image extraction paths. No complete accessibility or cross-browser certification is claimed.

## Remaining task scope

Task 1 now has the interface, mock proposals and uncertainty/output guards, but actual AI and real prompt-injection evaluation remain unfinished. Task 2 has bounded decoded intake, local rules, assessment history and failure handling; authentication and real-data private image storage remain absent. Task 3 has the synthetic customer flow; real extraction and live integration remain pending. Task 4 has a reproducible fixture-policy harness and authored typed baseline, not a model benchmark or human study. Task 5 has the resolution HTTP client and mock smoke, not actual-service integration or the final recorded demo. None of the five full tasks is claimed complete.

Next: account-owner-approved provider setup, bounded real adapter calls, reviewed image holdout and genuine output evaluation. Merchant remedy, balance, dispute, age, approval and payment checks remain Vismaya's responsibility. Arrange the daily 15-minute integration check directly; no messages or calendar events were sent by this task.

Ownership: feature changes are limited to `evidence/**`, `docs/rajiv/**` and `.github/workflows/evidence.yml`. Vismaya's lane, contracts, committed mocks, root dependencies/docs and shared CI have no authored feature changes.
