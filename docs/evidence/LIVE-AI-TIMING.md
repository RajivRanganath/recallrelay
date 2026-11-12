# Live-AI timing handoff — 9 November 2026

## Completed collection and analysis

The participant completed all twelve typed and twelve actual-AI tasks. All twelve AI requests returned usable proposals; there were no recorded failures, timeouts, withdrawals, skipped requests or retries. Median completion times were 8.0325 seconds typed and 4.8825 seconds AI-assisted. [EVALUATION-RESULTS.md](EVALUATION-RESULTS.md) and its linked machine-readable report retain errors, unresolved cases, per-case times, provenance and limitations. The completed mock pilot is separate and unchanged.

Actual browser autosaves were recovered from the local journal, preserving its original bytes and the final record's content. The original raw inputs, CSVs, provider call journal and frozen collector are retained under evidence/.local/human-ai-pilot-2026-11-09/. The importer checked all 24 scheduled tasks and successful browser proposals against twelve actual provider records, then the report recomputed final field/decision comparisons. Separate calculations matched medians and outcome counts. No new human interaction is needed for this pilot. Task #4 awaits contributor acceptance/merge; integration and recording in #5 remain deferred.

## Historical setup and scope

The collector used the existing OmniRoute image adapter, requested model gemini/gemini-3.1-flash-lite, loopback gateway port 20128, a 20-second adapter deadline, temperature 0, max_tokens 2048, reasoning_effort none and JSON-object output. The existing authorized key was read in place without copying it into the repo. Its gateway no_log flag was checked before launch. Preparation sent no images; the subsequent participant run made twelve recorded requests, all reporting served model gemini-3.1-flash-lite. No holdout or broad accuracy claim is supplied.

The sections below preserve the procedure used for collection. They are not an instruction to overwrite the completed run or repeat tasks.

## What the participant does

1. Open the collector's printed loopback customer URL. Complete the unscored typed practice.
2. Choose actual prior experience, personally check the local-observation consent box and begin the measured tasks. Preparation does not check that box.
3. For the twelve typed tasks, start the timer, transcribe readable model/batch identifiers, leave unclear values blank, confirm and check the match.
4. For the twelve AI-assisted tasks, start the timer and select Read label with AI once. Wait, inspect and correct the suggestion, then confirm and check the match. If extraction is unavailable, type readable values and retain the failure as part of the assigned AI arm.
5. Select Next task after reading each result. At the end download recallrelay-human-ai-timings.json and return it for validation/analysis. The loopback server also appends local snapshots, so completed records can be recovered if the download is missed.

Only the participant performs scored interactions. An early stop, timeout or failure stays in the record; retries need separate attempts and never replace first attempts. One request per assigned-assisted task avoids hidden retries. No request is made on typed tasks or during the unscored typed practice. The collector records actual returned proposal/source metadata and unavailable outcomes; merely showing AI configured does not prove a successful call.

## Provenance and offline analysis

The frozen local runner.py, study.js, study.css and metadata.json are hash-bound in configuration.json and each export. The original mock sources are preserved in their separate directory. provider-calls.jsonl retains the image hash, sanitized outcome, elapsed provider wait, proposal and returned source metadata, without full images or credentials. browser-snapshots.jsonl contains private local participant observations; do not commit raw files or aliases.

The prepared local export_records.py validates the returned download, frozen sources, exact image schedule and actual provider-call journal before generating sessions.csv, trials.csv and report.json in a new output directory. It checks successful browser proposals against the normalized provider record, retains unavailable calls and binds the journal hash. Run from the repository root using the evidence virtual environment, the actual downloaded JSON as the positional argument, and --output pointing to a new local directory. Do not run it with Python optimizations that disable assertions. Review raw records before publishing a redacted summary. This importer was subsequently applied to the completed autosaved observations. It generated the preserved local report and CSVs; the public summary omits private values.

## Recorded deviations and limits

Images are preloaded for both conditions outside the timer, excluding file selection. A browser monotonic timer runs from image reveal to the first visible assessment. Typed tasks run first, followed by reverse-order assisted tasks. One internal participant has already reviewed and timed these development images; learning and order remain confounded. These are explicit deviations from the original moderator/file-selection protocol, preserving the same rules as the prior pilot for usability. Session identity, consent and browser timing remain unauthenticated; hashes detect drift, not authenticity. Local instrumentation is retained but is not a publicly reproducible study package.

Report actual model/source metadata, proposal/unavailable counts, errors, unresolved decisions, edits, first attempts, noncompletion and retries. Provider wait is distinct from total human completion effort. Returned model IDs do not identify an immutable remote backend. Keep holdout and human_validated false; no causal savings, general accuracy or production claim follows. No resolution service, merchant storage or payment endpoint is used.

## Preparation checks

JavaScript and Python syntax checks passed. The launched page visibly reports AI via OmniRoute and presents an untouched practice/enrolment flow. That is a setup observation, not evidence of a completed provider call or human task. That preparation check made no provider call. The subsequent actual participant outcomes are reported above. No new local automated test suite, provider smoke run or integration check was performed for collector preparation.
