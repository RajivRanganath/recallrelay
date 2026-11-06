# Rajiv's evidence runbook

Checkpoint: 6 November 2026. Branch: `work/rajiv-evidence-intake`, based on pushed intake commit `1dc3155`. OmniRoute changes were verified locally before this feature commit. No public deployment, merchant message, payment, contract change, or other-lane edit occurred.

## Run and demonstrate

Default fixture/manual mode still needs no keys:

```sh
evidence/.venv/bin/python -B -m evidence.backend.server
```

Opt-in local setup reuses the existing IIT KGP env file in place:

```sh
evidence/.venv/bin/python -B -m evidence.backend.server --port 8111 --db evidence/.local/omniroute-demo.sqlite3 --extractor omniroute --omniroute-env '/Users/rajiv/Documents/Projects/Project(kgp)/.env' --model gemini/gemini-3.1-flash-lite
```

The existing key was not copied, printed, committed, or replaced. Only `OMNIROUTE_API_KEY` is read from the selected file; other provider credentials are ignored. No IIT KGP source or env file was changed. The gateway's metadata setting `no_log` was enabled for this key, after a startup environment attempt did not take effect. Five payload artifacts created by this session's synthetic tests were removed; older history and status summaries were preserved. Later observed gateway summaries had no request, response, or pipeline payload artifacts.

The gateway and evidence demo were left running on loopback at ports 20128 and 8111 at this checkpoint. For a later gateway restart, use the installed CLI on loopback:

```sh
OMNIROUTE_SERVER_HOST=127.0.0.1 omniroute serve --no-open --no-tray
```

Verify the key's payload logging remains disabled before sending images. The gateway package observed locally was 3.8.49. The IIT KGP text setup uses `auto/smart`; it initially returned no usable image proposals here, including an observed HTTP 429. The explicit image route above returned served model `gemini-3.1-flash-lite`. Model IDs and bridge-header observations do not identify an immutable backend revision or prove no internal rerouting.

Upload a synthetic fixture → **Read label with AI** → review model/batch suggestions and any clarification → separately confirm → deterministic manual campaign assessment. Proposals do not persist assessments. Missing or conflicting identifiers remain unresolved. Try typed entry when extraction is unavailable. Sample controls remain explicitly mock even in the AI-configured app.

The unchanged resolution mock can run separately on 8102. The evidence client reads its canned status only; it does not create a merchant case or move money.

## Verification and results

Final observed evidence suite: 70 tests on Python 3.11.16 with ResourceWarnings treated as errors. Shared contract checks: 3 tests. Fixture-policy replay: 12 cases / 60 checks / zero failures, still mock. Dependency consistency, JavaScript syntax, and whitespace checks passed. Initial sandbox attempts could not create temporary files or bind sockets; verification used approved temporary-file/loopback access instead.

Chrome checked AI configuration labels, separate confirmation, manual assessment after confirmation, edit invalidation, 503 field clearing with typed entry, photo removal, and mock configuration labels. AI success/failure responses in that browser check were explicit stubs. No page errors were observed. Genuine model calls were evaluated separately.

Final genuine provider development run: 12/12 proposals, 24/24 fields matching authored typed-entry references, zero unavailable calls, zero false eligible simulated outcomes against those references. Dataset: synthetic-labels-v1; prompt: label-image-2; temperature 0, max_tokens 2048, reasoning_effort none where supported, 20-second supervised wait, no client retries. This previously visible development set was used during request tuning. It is not a reviewed holdout or general accuracy result.

Earlier reports remain: auto/smart 0/3 usable proposals at 512 tokens; explicit vision route 2/3 at 2048 tokens with the preceding prompt. A diagnostic observed HTTP 200 plus finish_reason length; those incomplete responses were rejected. See [evaluation scope](../../evidence/evals/README.md) and [final report](../../evidence/evals/reports/omniroute-development.json).

```sh
evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -q
evidence/.venv/bin/python -B -m evidence.evals.run --check
evidence/.venv/bin/python -B -m unittest discover -s tests -q
node --check evidence/web/app.js
git diff --check
```

To repeat live calls, use the command in [evaluation instructions](../../evidence/evals/README.md) and a new report path. Preserve earlier reports, count unavailable calls, and inspect every field difference. Calls may consume provider quota.

## Remaining scope

Task 1 has a live image adapter and limited synthetic development evidence, including one instruction-bearing image; independently reviewed holdout and broader injection evaluation remain unfinished. Task 2 still lacks authentication and private real-data image storage. Task 3 remains synthetic; browser validation is bounded as described above. Task 4 still needs reviewed labels, holdout results, and a human study if making completion/savings claims. Task 5 still needs actual resolution-service integration, the daily integration check, and the recorded demo. None of the five full tasks is claimed complete.

Eligibility remains deterministic after human confirmation. Payment decisions, merchant approval, and resolution storage remain Vismaya's responsibility. No messages or calendar events were sent. Feature edits stay within `evidence/**` and `docs/rajiv/**`; contracts, mocks, root dependencies/docs, shared CI, and Vismaya's lane are unchanged.
