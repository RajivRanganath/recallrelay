# Live-AI timing handoff — 9 November 2026

## Status and scope

Issues #1–#3 are closed for the synthetic local prototype. The remaining non-integration requirement in #4 is an actual human typed-versus-AI comparison. The completed mock pilot in [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md) remains unchanged; merging its PR alone does not satisfy this requirement. Integration with the resolution service and the customer/joint recording are deferred at the owner's request. No new holdout or broad accuracy claim is required or supplied by this development pilot.

The separate local collector is evidence/.local/human-ai-pilot-2026-11-09/. It uses the existing OmniRoute image adapter, requested model gemini/gemini-3.1-flash-lite, loopback gateway port 20128, a 20-second adapter deadline, temperature 0, max_tokens 2048, reasoning_effort none and JSON-object output. The existing authorized key is read in place; it is never copied into the repo. Its gateway no_log flag was checked before launch. No images were sent and no timings generated during collector preparation.

## What the participant does

1. Open the collector's printed loopback customer URL. Complete the unscored typed practice.
2. Choose actual prior experience, personally check the local-observation consent box and begin the measured tasks. Preparation does not check that box.
3. For the twelve typed tasks, start the timer, transcribe readable model/batch identifiers, leave unclear values blank, confirm and check the match.
4. For the twelve AI-assisted tasks, start the timer and select Read label with AI once. Wait, inspect and correct the suggestion, then confirm and check the match. If extraction is unavailable, type readable values and retain the failure as part of the assigned AI arm.
5. Select Next task after reading each result. At the end download recallrelay-human-ai-timings.json and return it for validation/analysis. The loopback server also appends local snapshots, so completed records can be recovered if the download is missed.

Only the participant performs scored interactions. An early stop, timeout or failure stays in the record; retries need separate attempts and never replace first attempts. One request per assigned-assisted task avoids hidden retries. No request is made on typed tasks or during the unscored typed practice. The collector records actual returned proposal/source metadata and unavailable outcomes; merely showing AI configured does not prove a successful call.

## Provenance and offline analysis

The frozen local runner.py, study.js, study.css and metadata.json are hash-bound in configuration.json and each export. The original mock sources are preserved in their separate directory. provider-calls.jsonl retains the image hash, sanitized outcome, elapsed provider wait, proposal and returned source metadata, without full images or credentials. browser-snapshots.jsonl contains private local participant observations; do not commit raw files or aliases.

The prepared local export_records.py validates the returned download, frozen sources, exact image schedule and actual provider-call journal before generating sessions.csv, trials.csv and report.json in a new output directory. It checks successful browser proposals against the normalized provider record, retains unavailable calls and binds the journal hash. Run from the repository root using the evidence virtual environment, the actual downloaded JSON as the positional argument, and --output pointing to a new local directory. Do not run it with Python optimizations that disable assertions. Review raw records before publishing a redacted summary. Until real observations exist, no human AI timings can be analysed or claimed.

## Recorded deviations and limits

Images are preloaded for both conditions outside the timer, excluding file selection. A browser monotonic timer runs from image reveal to the first visible assessment. Typed tasks run first, followed by reverse-order assisted tasks. One internal participant has already reviewed and timed these development images; learning and order remain confounded. These are explicit deviations from the original moderator/file-selection protocol, preserving the same rules as the prior pilot for usability. Session identity, consent and browser timing remain unauthenticated; hashes detect drift, not authenticity. Local instrumentation is retained but is not a publicly reproducible study package.

Report actual model/source metadata, proposal/unavailable counts, errors, unresolved decisions, edits, first attempts, noncompletion and retries. Provider wait is distinct from total human completion effort. Returned model IDs do not identify an immutable remote backend. Keep holdout and human_validated false; no causal savings, general accuracy or production claim follows. No resolution service, merchant storage or payment endpoint is used.

## Preparation checks

JavaScript and Python syntax checks passed. The launched page visibly reports AI via OmniRoute and presents an untouched practice/enrolment flow. That is a setup observation, not evidence of a completed provider call or human task. No new automated test suite, provider smoke run, participant result or integration check is claimed in this preparation.
