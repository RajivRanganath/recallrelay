# Connection-recovery check cleanup — 9 November 2026

The evidence workflow on documentation commit bbfc7cd failed in test_capacity_recovers_after_rejected_and_disconnected_requests at peer.shutdown with Linux ENOTCONN. The socket may already be disconnected by server rejection or the receive watchdog before that cleanup operation. The check then never reached its recovery assertions.

Allow only ENOTCONN from that shutdown call; every other socket error still propagates. Keep the health/capacity recovery, no-persisted-assessment and final successful assessment assertions unchanged. No time budget, runtime, mock, contract, provider behavior or human timing instrumentation changes.

The observed failed workflow is https://github.com/RajivRanganath/recallrelay/actions/runs/42606076096. This patch changes an existing test rather than adding new tests. Python syntax and whitespace checks passed; hosted checks on this PR provide the execution result. No local automated test suite or provider call was run for this patch.
