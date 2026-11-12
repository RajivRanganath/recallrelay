# Customer demo rehearsal

## Current combined walkthrough: 12 November 2026

Use [FINAL-DEMO.md](FINAL-DEMO.md) for the current same-case customer and merchant recording outline. It uses the integrated launcher, explicit saved-assessment handoff, merchant approval and customer status. [HANDOVER-CHECKPOINT.md](HANDOVER-CHECKPOINT.md) records current verification and remaining work. No finished recording is claimed.

## Historical standalone outline

Current checkpoint, 9 November 2026: standalone evaluation work now includes a completed actual-provider human timing pilot; see [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md). Integration with the resolution lane and recording remain deferred at the owner's request. The rehearsal instructions below do not constitute a completed joint demo.

This is the first 75 seconds of the synthetic RecallRelay demo. The timing below is a recording outline, not a measured user-completion result or a finished recording. No real product, customer, payment or AI recognition is shown in the default rehearsal.

## Start from a clean checkout

From the repository root, use Python 3.11 and install only the evidence lane's locked dependencies:

```sh
python3.11 -m venv evidence/.venv
evidence/.venv/bin/python -m pip install -r evidence/requirements.lock.txt
evidence/.venv/bin/python -B -m evidence.demo
```

Open the customer URL printed by the launcher. Both servers bind to loopback and default to available ephemeral ports; `--port 8111` selects a fixed customer port when needed. The command starts the real evidence app with mock fixture extraction and the unchanged committed resolution mock. It explicitly selects those adapters even if provider or resolution environment variables exist. It reads no provider key and makes no live AI/payment request.

The evidence database starts empty in a temporary directory for each launch. Ctrl+C stops the owned servers and removes that directory; restarting resets the rehearsal. Reloading the page resets the form but retains that session's temporary assessment history. Use samples for the timed outline so a file chooser does not interrupt it. A separate photo variant can use a repository image from `evidence/evals/fixtures/`; default suggestions remain exact-byte lookup, not OCR.

## First 75 seconds

| Target | On screen | Narration |
|---|---|---|
| 0–10 s | Show the synthetic notice and empty confirmation form. | “RecallRelay starts with product-label evidence. These products and orders are fictional. This rehearsal uses mock suggestions and manual rule checks.” |
| 10–27 s | Clear label → Use sample → review LAMP-100/B101 → separately check confirmation → Check campaign match. | “Suggestions are only a starting point. I confirm both identifiers before deterministic rules check the approved campaign. Matching identifiers do not authorize a refund.” |
| 27–45 s | Unreadable batch → Use sample → leave batch blank → confirm → Check campaign match. | “An unreadable batch stays blank. The result asks for that one detail instead of guessing or marking the product eligible.” |
| 45–60 s | Excluded batch → Use sample → confirm B103 → Check campaign match. | “This batch is outside this campaign. That is a campaign decision, not a statement that the product is safe.” |
| 60–75 s | Scroll to Resolution status → Read demo case status. Keep the separate-record warning visible. | “Status is read through a separate service. This mock merchant record is separate from the assessment. Merchant review and payment decisions belong to the second half.” |

Pause recording and reset if a step fails. Keep the missing field, manual assessment mode and mock status labels readable. Do not edit out a failure while describing the sequence as an uninterrupted successful run. The sample controls and canned merchant record do not establish an automatic handoff.

## Optional actual-service status rehearsal

The customer launcher can read an already-running local resolution service:

```sh
evidence/.venv/bin/python -B -m evidence.demo --resolution-url http://127.0.0.1:8102
```

The URL must be an explicit loopback HTTP origin. No internal resolution mock is started in this mode. The launcher never starts, seeds, approves or stops that external service; it owns only its temporary evidence app. Until the merchant supplies a reviewed case, status may correctly return 404. Label assessment remains independent of that dependency. A saved merchant review may also refer to an earlier evidence snapshot; status alone does not establish that the current assessment was handed off.

Reproducible HTTP compatibility with resolution commit `e1e16be6928afcdd52015097a3bbab6b42ddbd8b` is documented in [INTEGRATION.md](INTEGRATION.md). That test coordinator explicitly supplies a handoff. The confirmed concurrent-reconciliation state-regression finding is still resolution-owner follow-up; this rehearsal does not exercise approval or reconciliation. A real sandbox demonstration requires the resolution owner's adapter, appropriate synthetic sandbox IDs and read-back evidence.

## Verification and remaining work

The launcher checks cover fresh state, explicit mock selection despite inherited configuration, usable sample/assessment/status paths, cleanup, repeated starts, externally owned service lifetime, partial-startup cleanup and invalid port/origin rejection. Browser rehearsal covers clear, missing and excluded batches, separate confirmation and visibly simulated merchant status. This is rehearsal evidence only; no video, spoken-duration measurement, real provider result, human study, joint merchant demo or sandbox refund is claimed.

After a clean rehearsal: record this customer half with visible mode labels, agree the transition with the merchant half, and preserve failures and provider mode in the submission notes. Independent holdout review and human completion/effort measurement remain separate pending work.

## Customer-to-merchant recording transition

Before a joint recording, agree the code revisions, visible mock/provider labels, case ID and explicit handoff method with the resolution owner. The customer launcher only reads status: its successful assessment is not a merchant-case creation event. Show or narrate the explicit coordinator/merchant action, the assessment snapshot ID and whether the merchant view refers to it. If using the committed mock, say that its case is separate and canned. Do not present a cut between unrelated cases as an automatic end-to-end handoff.

Rehearse the customer portion using the outline above, retain a visible unresolved/excluded example, and time the actual take. Record take duration and failures separately from human task timings. The merchant owner controls remedy approval, refund actions and any sandbox evidence. Stop the customer launcher with Ctrl+C after the take. A finished video and joint sign-off remain human/team deliverables.
