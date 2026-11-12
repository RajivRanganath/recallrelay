# Actual-service HTTP integration

## Current integration: 11 November 2026

Use [FINAL-INTEGRATION.md](FINAL-INTEGRATION.md) for the one-command two-app launcher, explicit customer handoff, merchant approval and customer status walkthrough. It uses actual services, separate stores and fake payments, based on merged main `f29a9f3`. The integration branch also updates evidence CI's source pin to that merged revision. Recording and joint acceptance remain separate.

## Historical smoke checkpoint: 8 November 2026

This evidence-owned check uses resolution commit `e1e16be6928afcdd52015097a3bbab6b42ddbd8b` (Vismaya's review/approval/fake-PayPal implementation) and evidence based on merged main `171b5ea2868beb9664ab9884f43610b20284207d`. Resolution source is exported read-only into a separate directory; its branch and tracked files are untouched. No resolution PR existed when checked on 8 November 2026. This is local compatibility evidence for that commit, not a merge or release of the resolution lane.

## Reproduce without providers

Use the installed evidence Python 3.11 environment and locked lane dependencies. Fetching updates requires repository access; the tests themselves use only loopback HTTP and temporary files.

```sh
git fetch origin work/vismaya-resolution
mkdir -p evidence/.local/integration-resolution-e1e16be
git archive e1e16be6928afcdd52015097a3bbab6b42ddbd8b resolution contracts | tar -x -C evidence/.local/integration-resolution-e1e16be
RECALLRELAY_RESOLUTION_SOURCE="$PWD/evidence/.local/integration-resolution-e1e16be" evidence/.venv/bin/python -B -W error::ResourceWarning -m unittest discover -s evidence/tests -p 'test_resolution_service.py' -v
```

The source variable must point to the directory containing `resolution/` and `contracts/`. When omitted, these six optional checks are explicitly skipped so the ordinary suite remains usable without the other lane's unmerged code. When set to a missing or invalid source, startup fails rather than substituting a mock. Evidence CI separately checks out the exact commit above, passes the source variable, and runs these checks with the full suite. Moving to newer resolution code requires an intentional pin update and rerun.

Each test starts the actual resolution HTTP server in an isolated Python subprocess and the actual evidence HTTP server on separate ephemeral loopback ports. Each service owns a different temporary SQLite database; the coordinator inspects neither database. A separate subprocess runs the actual resolution `EvidenceClient` against evidence over HTTP. A test coordinator then explicitly posts the resulting assessment plus the synthetic order and merchant remedy confirmation to `/v1/resolutions`. The customer status route reads that service through the existing supervised `ResolutionClient`.

The resolution subprocess receives a minimal environment with no inherited provider keys, an isolated import path, and a test adapter that records and rejects any refund attempt. Tests fail if that adapter is invoked. No approval or reconciliation endpoint is called. These checks use typed confirmed identifiers, manual evidence assessment and mock-mode resolution review; no image extraction or AI provider runs.

## Observed scenarios

On 8 November 2026, all six tests passed locally with Python 3.11.16 and ResourceWarnings treated as errors:

| Scenario | Observed behavior |
|---|---|
| Eligible identifiers and explicit handoff | Missing case initially returns 404. The merchant client obtains the persisted manual assessment. Missing remedy confirmation stays `manual_required`; confirmed remedy returns `awaiting_approval` for 4000 USD minor units. Repeated review returns the same response. |
| Frozen handoff and status reads | The review cites the supplied assessment ID. A later evidence edit produces a new assessment while resolution retains the supplied snapshot. Customer status reads leave the current evidence assessment unchanged. |
| Missing confirmed batch | Evidence returns `needs_information` with a batch clarification; resolution stays `needs_information` with zero proposed amount. |
| Excluded batch | B103 stays `excluded` through both services with zero proposed amount. |
| Remaining amount and order age | With 1500 already refunded from 4000 minor units, review proposes 2500. A separate 181-day-old eligible order requires manual handling with zero proposed amount. |
| Wrong-case handoff | A mismatched assessment case gets HTTP 400; the existing review and evidence assessment remain unchanged. |
| Resolution stopped | Customer status returns a visible 503; stored evidence remains readable and a new typed assessment still succeeds. |

All reviewed responses remain mock mode with null operation/refund IDs. The payment-denying adapter recorded no attempts. Processes, HTTP servers and temporary databases are cleaned up. This is seven scenario rows across six test methods, not seven independent trials.

## Limits and next steps

The coordinator supplies the merchant handoff explicitly; there is no new automatic customer-to-merchant case creation or production orchestration. Retaining a supplied assessment snapshot is an observed behavior, not a freshness or approval guarantee. The tests do not validate merchant UI, approval/refund execution, PayPal sandbox behavior, live payments, authentication, private-data use, concurrent cross-service workflows, AI extraction quality or user completion time. The fake-payment implementation's own tests and reviews remain the resolution owner's responsibility.

Actual service compatibility is now checked for these review/status paths at the pinned commit. A jointly reviewed integration, merchant UI/demo, feature freeze, separately reviewed holdout labels and recorded demo remain pending. No other contributor's source, shared contract, mock or root dependency changes here.
