# Final handover checkpoint

Checked 12 November 2026. This records observed implementation and verification, not production acceptance or a finished submission.

## Source and integration

- Main `9d8033c` includes PRs #29–#34. PR #34 merged at `d408859`, before its last correction was pushed.
- Vismaya's final branch `work/vismaya-webhook-exception` ends at `521393a9db8f02ae10a105f8b29a87a6993b570c`. That last commit is **not yet on main at this checkpoint** and needs a follow-up integration PR.
- The correction preserves receive timeout state and rejects an incomplete request with 408 before dispatch. Previously, an unfinished header block could time out and still confirm remedy conditions.
- The exact previous reproducer against `521393a` returned 408 and left remedy confirmation false. Five new regressions cover confirmation, approval, data reads, webhook verification and a complete valid request.
- Permanent ownership has not been transferred in AGENTS.md. Lane rules and explicit scoped exceptions still apply.

## Verification of the handed-over source

The commit was exported into a separate temporary directory. Tests used local synthetic stores and providers. Application services retained separate storage and communicated over HTTP.

| Scope | Result | Environment |
|---|---|---|
| Evidence suite, actual merchant source enabled | 161 passed, 82.098 seconds | macOS, Python 3.11.16, ResourceWarnings treated as errors |
| Merchant suite | 169 passed, 90.864 seconds | Same local Python environment; fake/stub providers |
| Shared contract/mock tests | 3 passed, 1.042 seconds | Local Python |
| Customer and label-review UI tests | 10 passed | Node 26.7.0 |
| Fixture policy replay | 12 cases / 60 checks, zero failures | Mock lookup; no image recognition or accuracy measurement |
| Unfinished-request reproducer | 408, remedy confirmation stayed false | Temporary case, 0.3-second receive budget |
| Browser same-case flow | Handoff, advisory template, wrong-amount rejection, fake refund and customer status observed | Actual services, separate temporary stores |

The owner branch's [resolution CI](https://github.com/RajivRanganath/recallrelay/actions/runs/43083876271) and [shared checks](https://github.com/RajivRanganath/recallrelay/actions/runs/43083876414) succeeded at `521393a`. Hosted CI is separate from local results and Windows evidence reported in the owner's runbook. Three symlink tests can error on a Windows account without symlink permission; earlier hosted Windows evidence checks used a runner with that capability.

The handover follow-up pins both evidence CI platforms to that same final merchant commit for the six actual-service integration checks. Consult the current PR #35 checks for the exact Linux/Windows result; earlier green runs against an older merchant snapshot do not replace it.

## Read-only PayPal sandbox check

On 12 November 2026, the local credentials file was used for sandbox authentication and read-only capture/order/refund-history calls. Credentials, tokens and full provider responses were not printed or committed. No refund, payment, webhook registration or public access was created by this check.

| Capture | State | Paid | Refunded | Remaining |
|---|---|---:|---:|---:|
| `49Y84274VH780010F` | REFUNDED | 40.00 USD | 40.00 USD | 0.00 USD |
| `6WJ74541HH375824T` | PARTIALLY_REFUNDED | 40.00 USD | 20.00 USD | 20.00 USD |

These observations do not authorize a refund. Re-read provider state before a separately approved sandbox operation. Keep credentials outside the repository with owner-only access. Replace values pasted into chat; never include them in a runbook, PR, output or recording.

## Runtime and demo

Use [FINAL-INTEGRATION.md](FINAL-INTEGRATION.md) for installation and the one-command launcher. [FINAL-DEMO.md](FINAL-DEMO.md) supplies a 150-second target outline with both halves linked by one assessment. It is a script, not a measured or recorded take. The [old standalone outline](DEMO.md) remains historical.

The launcher uses mock label lookup, confirmed-text rules, template briefs and fake payments. Historical live-AI and sandbox reports remain separate and unchanged. No evaluation is rerun or reattributed by the handover.

## Remaining acceptance

1. Integrate `521393a` through a follow-up PR and verify its current CI. Until then, main retains the last reported malformed-request regression.
2. Complete the documentation checkpoint and correct the demo issue state: #5 and #10 include recording, which has not happened.
3. Real sandbox webhook delivery is unverified. The [proposal](../vismaya/WEBHOOK-EXCEPTION.md) is preparation, not execution approval. An approved operator, temporary host, exact callback confirmation, registration, permitted refund and cleanup are required. The local integrated demo is not that test.
4. Record the final demo and obtain required acceptance. Submission destination and event-specific requirements were not supplied; do not invent them or submit automatically.

## Retained limitations

No merchant authentication, production deployment, real customers, live-money mode, general AI accuracy, causal savings, exactly-once guarantee, live open-dispute trial or mobile visual acceptance is claimed. Merchant OmniRoute setup was not completed. Existing evaluations use synthetic development cases, not an independent holdout. Cleanup of processes, Docker images and stashes on the other machine remains with its operator; none was removed from this Mac by this handover.
