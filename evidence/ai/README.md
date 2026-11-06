# Label extraction boundary

`extraction.LabelExtractor` receives only a decoded synthetic image. No campaign, order, approval state, database handle, or payment tools enter the adapter. Default extraction remains exact-byte fixture lookup in `mode: mock`.

The opt-in `OmniRouteExtractor` uses the existing local gateway at `http://127.0.0.1:20128/v1`. `read_key` reads only `OMNIROUTE_API_KEY` from the process environment or an explicitly supplied env file; it does not execute the file, import other providers' keys, copy credentials, or persist secrets. No new runtime dependency was added.

## Output and failure boundary

The lane-local schema requires exactly model and batch, each with value, confidence, and uncertain. Extra approval/tool fields, malformed JSON, duplicate keys, non-finite confidence, refusals, tool calls, and incomplete generation are rejected. Missing/uncertain/ambiguous/below-threshold values stay blank with one clarification. The 0.85 threshold and model confidence are uncalibrated.

Live calls use inline image bytes, a versioned instruction to treat image text as data, JSON output, temperature 0, a 2048-token output request, and reasoning disabled where supported. No tools or client retries are supplied. One supervised spawned worker handles each call; at most two calls run per adapter. The parent waits at most 20 seconds for a result, then terminates and reaps the worker. Local termination does not cancel accepted upstream work or guarantee billing cancellation. Responses are limited to 64 KiB; redirects, partial HTTP success, wrong content types, and inconsistent framing fail closed.

Only an allowlisted failure code survives for evaluation diagnostics. Provider bodies, exceptions, keys, and image bytes are never emitted by the adapter. There is no automatic fixture fallback in AI mode. Typed entry remains available.

Successful proposals record the requested and served model IDs, prompt version, whether a modality-bridge header was observed, and whether the model IDs match. These observations do not establish a pinned upstream revision or prove the absence of internal rerouting. The [OmniRoute maintainer explains why actual served models matter for vision](https://github.com/cheaper-inference/OmniRoute/discussions/6096).

## Gateway logging prerequisite

Before sending images, disable request/response payload logging for the gateway key using its `no_log` setting. This is separate from RecallRelay's own no-body logging. The reused local key has that setting enabled; a startup environment attempt alone did not take effect in the observed session. Verify the gateway summaries contain no payload artifacts. Upstream provider retention is outside this application's control.

See [setup](../README.md), [evaluation scope](../evals/README.md), and [Rajiv's checkpoint](../../docs/rajiv/RUNBOOK.md).
