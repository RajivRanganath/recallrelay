# Resolution service: merchant review, approval and refunds

Merchant decision and settlement: deterministic review, human approval, an idempotent refund state machine, an advisory merchant brief, and a merchant review UI. By default payments use a **fake PayPal adapter** and the brief is a **template**. A PayPal **sandbox** adapter (one refund verified against the real sandbox on 9 November 2026) and an **AI brief** via OmniRoute or direct Gemini (evaluated four times on a real Gemini model, latest run 12 of 14 drafts accepted, with the checker changed between runs and then frozen; in the running app, one "Write brief" on the demo case on 9 November 2026 returned an accepted AI draft) are opt-in. See [the runbook](../docs/resolution/RUNBOOK.md) for what is tested and what is still missing, and [LIVE-CHECKS.md](../docs/resolution/LIVE-CHECKS.md) for the real-service checks.

```sh
python -m resolution.backend.server --port 8102
python -m unittest discover -s resolution/tests -v
python -m resolution.evals.run --provider template --output resolution/evals/reports/NEW_NAME.json
```

Layout: `backend/` (review, store, refund, fake and sandbox PayPal, evidence client, server), `ai/` (brief validator, OmniRoute and Gemini clients), `web/` (merchant UI), `evals/` (labeled cases and runner), `sandbox/` (scripts for a real sandbox payment and refund read-back), `tests/`. Never import the evidence service directly; talk to it over HTTP (`EVIDENCE_BASE_URL`). Secrets live in env files outside the repo, are read for named variables only, and are never committed.
