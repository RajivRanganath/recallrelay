# Full Windows evidence coverage

Maintenance branch: `work/rajiv-windows-suite`, based on the integrated prototype and updated with merged merchant replay hardening. This work changes only evidence code/tests/evaluation preparation, Rajiv documentation and evidence CI.

## Reproduced failures

The first full native Windows run attempted all 157 existing evidence tests with the six actual-resolution checks enabled. It reported nine failure outcomes and one error: the dangling-symlink test generated two failures, total-budget socket tests produced a timeout and a five-second cleanup failure, and six legacy actual-service tests could not start their isolated merchant process. This is the observed CI result, not a claim that the earlier reported six Windows failures exhaust all platform behavior. The first diagnostic run is [43068226125](https://github.com/RajivRanganath/recallrelay/actions/runs/43068226125).

## Fixes and retained checks

- Use a reader thread for the older actual-service test process, just as for the integrated launcher. Preserve only Windows system/temp variables in its minimal environment; no provider keys are inherited.
- Recompute the remaining total receive budget before every raw socket read, including reads inside buffered header lines. Restore the original socket timeout after intake finishes. The watchdog remains, but deadline enforcement no longer relies only on shutdown interrupting an already blocked read. A regression disables the watchdog's shutdown wakeup and still requires bounded cleanup, a deadline rejection, and capacity release.
- Windows report and plan creation use native `CREATE_NEW` with `FILE_FLAG_OPEN_REPARSE_POINT`, rejecting an existing final-path link instead of following a dangling target. Handle ownership passes to the standard Python file stream and is closed on every setup failure. POSIX retains exclusive `open('x')`. The original before-credential/call assertions, dangling-link preservation checks, incomplete-report tests and competing-run checks remain. Two added native reservation tests preserve existing file/directory bytes and admit one creator from eight concurrent attempts. See [Microsoft's API reference](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
- The Windows job runs the **full** evidence suite, six actual-service checks, fixture-policy replay and ten Node UI checks. It uses read-only repository permissions, no secrets and a ten-minute ceiling. Both platforms pin the same merged merchant snapshot.

The corrected full native Windows job passed at `e358a4e`, including the 160-test suite, fixture replay and ten Node UI checks: [run 43069623220](https://github.com/RajivRanganath/recallrelay/actions/runs/43069623220). No tests were skipped to obtain that result. The final pin/documentation checkpoint uses the same runtime changes against the newer merged merchant snapshot; consult the latest PR #32 checks for that exact head.

A later full rerun exposed an intermittent wire-level difference in the incomplete-request shutdown test: bounded cleanup completed, but Windows returned an empty connection close instead of the expected HTTP 408 bytes. The test now accepts a closed/reset connection or an actual 408, while retaining both elapsed-time bounds and adding an explicit no-assessment-persisted assertion. Any nonempty successful/unexpected HTTP response still fails. No timeout or successful request is accepted, and no test is skipped.

The paired push/PR rerun also exposed Windows `ConnectionAbortedError` when an overloaded connection was closed with unread input, including a health probe racing handler cleanup. Overload checks now accept only a 503 or reset/abort/closed connection, still require exactly two admitted application calls and zero persistence before release, and require a genuine healthy response within the existing recovery window. A new deterministic peer check verifies that overload formats a 503 without admitting a handler, independent of whether a real TCP peer receives the best-effort bytes. Timeouts, arbitrary errors and successful excess requests remain failures. The final suite has 161 tests.

## Local evidence and evaluation provenance

Python 3.11.16 on macOS: 160 evidence tests passed in 81.381 seconds with ResourceWarnings treated as errors and actual-service checks enabled. The focused receive-deadline tests passed, including the missing-wakeup regression; 19 evaluator/output tests and two native reservation tests passed. Existing merchant hardening separately passed 142 tests before merge in #30.

Output-reservation changes alter evaluated source. The old v1/v2 plans and all measured reports remain byte-for-byte unchanged. A new **development-v3** plan freezes the updated code and helper offline with the same twelve development images and existing public model configuration; `holdout` and `human_validated` remain false. It records no model call, new accuracy estimate or human timing. The old plan correctly fails against newer source; no historical result is reattributed to this version. Exact platform/runtime bindings remain enforced.

Real webhook delivery is still blocked by the missing approved callback and registration documented in [the shared prerequisites](../WEBHOOK-VERIFICATION.md). Final recording remains deferred. These maintenance checks do not provide production, live-money or exactly-once guarantees.
