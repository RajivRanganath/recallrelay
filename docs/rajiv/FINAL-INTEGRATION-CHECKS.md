# Final local integration checks

11 November 2026. Base: merged main `f29a9f3ee0dd46c9fd86b86588f4d30ae3eb94d1`. Branch: `work/rajiv-final-integration`. Python 3.11.16 with existing installed lane dependencies. These are local results; no hosted CI, new provider measurement, fresh dependency install or production claim is implied.

| Check | Result |
|---|---|
| Full evidence Python suite, including six existing actual-merchant checks and eight new handoff/launcher tests | 148 passed, 0 skipped, ResourceWarnings treated as errors |
| Existing resolution Python suite, including five actual-evidence checks | 135 passed, 0 skipped, ResourceWarnings treated as errors |
| Existing shared contract/mock suite | 3 passed |
| Node UI checks: customer async state/handoff and label-review page | 10 passed |
| Synthetic fixture-policy replay | 12 cases, 60 checks, 0 failures |
| Frozen development-v2 plan | Verified unchanged; 12 cases, holdout false, human_validated false |
| Dependency consistency and customer JavaScript syntax | Passed |

The first focused full-flow test attempt used an invalid zero approval amount and expected a lifecycle refusal; the merchant correctly returned HTTP 400 for invalid input. The test was corrected to use a valid positive amount, then passed. No merchant source change was needed. A provisional shared validator edit also caused the frozen evaluation plan to reject its changed fingerprint; that edit was removed and the handoff validator was isolated in its own client. The original plan then verified without changing its inputs, source list, flags or fingerprint.

The full evidence suite was rerun after the final runtime changes and new bounded POST tests: 148 passed in 72.939 seconds. Merchant suite: 135 passed in 71.535 seconds. Shared suite: 3 passed in 1.043 seconds. Node: 10 passed. Earlier successful runs remain earlier checks; they are not additional independent observations.

## Browser rehearsal

Actual customer and merchant servers, not an HTTP stub; separate temporary databases, mock extraction, template brief and fake payments. Checked: clear sample → explicit identifier confirmation → persisted assessment → Send for merchant review → same assessment shown in merchant case → remedy confirmation → incorrect amount blocked → exact 40.00 USD fake approval → customer reads refunded status for the same case. The operation and fake refund ID were visible in the merchant result. No real person review/timing observation is claimed by this automated UI rehearsal.

## Boundaries

No resolution/shared application source changes, no provider credentials, no real AI or PayPal calls, no deployment and no changes to historical evaluation reports. Merchant approval and payment rules stay in the merchant service. Real PayPal webhook delivery, final demo recording, cross-contributor acceptance and production operation remain outside this check. See [the runbook](FINAL-INTEGRATION.md) for retry uncertainty and temporary-state behavior.
