# One RecallRelay workspace

The integrated launcher now presents one application URL and one navigation for the complete case: **Check label → Merchant review → Refund status**. There is no second merchant tab, case seeding button or manual case selection in this workspace. Both roles use the submitted assessment and the same canonical merchant case/operation.

## Start

Use the existing evidence environment, or create it with the repository's locked requirements. From the repository root:

```sh
evidence/.venv/bin/python -B -m evidence.integrated --port 8101
```

Windows PowerShell:

```powershell
.\evidence\.venv\Scripts\python.exe -B -m evidence.integrated --port 8101
```

Open the single printed **RecallRelay** URL. Use `--port 0` to choose an unused application port. Internal customer and merchant ports are selected automatically; the optional `--merchant-port` remains for local diagnostics. Ctrl+C stops the workspace and its two services and removes the temporary session stores.

## Complete one case

1. Use the clear synthetic example, or upload a synthetic PNG/JPEG and type its identifiers. Example/fixture suggestions are mock; no general OCR or external AI runs here.
2. Check model and batch, explicitly confirm them and check the campaign match.
3. Select **Send for merchant review**. The workspace opens **Merchant review** with that exact assessment already loaded.
4. Read the evidence, order and optional template brief. A matching label alone does not satisfy remedy conditions. Explicitly confirm the conditions only after checking them.
5. Type the exact shown refund amount and an approver name, then select **Approve fake refund**. The workspace opens the shared outcome and reads customer status back through the existing HTTP client.
6. Pending cases receive passive status reads while that view is visible. Reconciliation requires a separate click. No tab switch, brief generation or status refresh approves a refund.

Unreadable identifiers stay unresolved; excluded batches stay excluded. The merchant cannot approve these cases. A label edit invalidates the current browser assessment; it does not rewrite a submitted merchant outcome. Reloading restores the latest saved assessment and reads the same merchant case. No browser local storage holds images, names or records.

## Implementation boundary

The workspace is served by an evidence-owned, loopback-only gateway that calls the existing customer and merchant APIs over HTTP. It has no application database and never imports merchant code. Services retain their own SQLite stores, dependency files and frozen v1 payloads. Standalone lane UIs remain usable for development; the integrated user journey uses one URL and a new shared frontend, not embedded copies of those pages.

The gateway forwards only explicit allowlisted JSON routes to fixed loopback origins. It rejects foreign/duplicate Host or Origin, transfer encoding, duplicate/oversized body framing and incomplete intake. No arbitrary proxy target, merchant fixture seeder or PayPal webhook route is exposed through it. Secrets, cookies and browser authorization headers are not forwarded. This is a local prototype, without login or production deployment.

All integrated modes remain explicit: mock extraction, template briefs, fake payments. The separate real sandbox delivery experiment in [the measured webhook record](../WEBHOOK-RESULTS.md) does not make this launcher a real-payment or publicly deployed app. No new provider call or paid service is required.

## Verification: 12 November 2026

- 168 evidence tests passed on Python 3.11.16/macOS, ResourceWarnings treated as errors, including seven new workspace HTTP/integration checks. The existing customer/merchant integration and startup tests remain usable.
- 16 dependency-free Node UI state tests passed, including six new workspace checks for restored same-case state, edit invalidation, exact-amount binding, passive navigation/polling, stale-brief invalidation and lost approval response recovery without automatic retry.
- Fixture policy replay passed 12 cases / 60 checks. JavaScript syntax and whitespace checks passed. No merchant source, frozen v1 contract or root dependency changed; the merchant suite was not rerun for this frontend/gateway change.
- The actual browser walkthrough used one URL and tab: clear example → confirmed assessment → automatic same-case merchant review → template brief → explicit remedy confirmation → 39.99 refused → explicit 40.00 fake refund → matching customer/merchant outcome. Reload restored the settled case without a new refund.
- Initial test authoring had one HTTP assertion with an invalid zero-amount precondition and two asynchronous DOM-double assertions that read before the action completed. Those test fixtures were corrected; the complete 168-test and 16-test runs above then passed. The stale-brief display found during browser review was fixed and covered by a regression.

These checks measure the local synthetic workflow. They are not new AI accuracy, human timing, live-payment or production acceptance results. Native Windows execution is left to the PR's full-suite CI job; do not infer it from the local Mac run.

### Post-merge Windows observation

Both Windows PR runs for #39 passed. The first post-merge Windows run (`43166431720`) then passed 167/168 tests: the unfinished-header workspace test expected a complete HTTP 408 but received a closed connection. All other workflow tests passed. Its regression was corrected to accept bounded rejection/close while directly asserting zero upstream connection attempts, single-handler capacity recovery, continued root-page availability, and explicit rejection of the separately truncated body. A socket timeout or forwarded request still fails. This changes only the test and this record; application and payment code are unchanged. Follow-up native CI is the authority for the corrected check.
