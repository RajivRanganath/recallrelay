# Customer evidence UI

Buildless HTML/CSS/JS served by `python -m evidence.backend.server` from the repository root. No Node packages or frontend build are required. Use synthetic data only.

The UI covers mock sample suggestions, transient photo preview, a known-fixture extraction button, typed identifiers, explicit confirmation, one targeted clarification, assessment result and resolution status/error display. All dynamic evidence and provider text uses `textContent`. Editing identifiers hides stale results and requires confirmation again. The browser cannot submit campaign/order flags through the demo endpoint.

Native form controls, visible focus rings, live status text and responsive stacked/two-column layouts. See [the runbook](../../docs/rajiv/RUNBOOK.md) for browser verification scope. This is a local prototype with no customer authentication, genuine OCR or automatic merchant case creation.

The image-suggestion button calls `/demo/image-extraction`, clears prior suggestions/results/confirmation and labels its output as fixture-only. Conflicting/low-confidence fields remain blank. Unknown-image and provider failures show an error without prefilled fields. No genuine OCR is running.
