# Customer evidence UI

Served by the evidence backend on loopback; no separate framework or runtime dependencies.

The UI reads the configured extraction mode from `/health`. Mock samples remain explicitly mock. Image suggestions use either exact fixture lookup or opt-in OmniRoute AI, labeled separately. AI success displays the served model and warns that confidence is self-reported and uncalibrated. Health reports configuration, not provider reachability.

Uploading only prepares a preview. The user selects the suggestion button to submit a synthetic image. Suggestions never check the confirmation box or create an assessment. Editing identifiers, replacing an image, and extraction failure clear old authority. The image request waits up to 40 seconds so the backend's supervised 20-second call can finish; other requests retain an 8-second browser timeout.

The observed Chrome check used explicit stub AI success/failure responses to verify mode labels, separate confirmation, manual assessment, edit invalidation, failure handling, photo removal, and mock labels. Genuine provider calls were evaluated separately. No new cross-browser or full accessibility certification is claimed.

Configuration responses cannot replace a loaded sample or photo provenance note. A late valid health response enables image suggestions after preview preparation without unlocking a busy operation; invalid configuration keeps extraction disabled and typed entry usable. Run the dependency-free asynchronous state regressions with `node --test evidence/tests/test_web.js`. These tests use DOM doubles and do not replace a rendered browser check.

Resolution `mode: mock` is displayed as simulated resolution with no real payment. That mode can describe either the canned mock service or a persisted review/fake-payment result from the actual resolution implementation. The UI preserves the warning that this separate record does not prove a handoff from the current assessment.
