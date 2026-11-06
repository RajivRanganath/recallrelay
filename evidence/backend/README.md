# Evidence backend

Run from the repository root with `python -m evidence.backend.server` after installing `evidence/requirements.lock.txt` in your lane environment. See [the evidence README](../README.md) for setup and limits.

- `validation.py`: frozen schemas and confirmed-field validation; no remote schema fetching.
- `images.py`: PNG/JPEG integrity and pixel decoding, format/dimension/size/animation limits.
- `json_input.py`: strict JSON without duplicate keys or non-finite constants.
- `assessment.py`: confirmed identifiers + deterministic rules; always `mode: manual`.
- `store.py`: evidence-only SQLite history, conflicts and restart reads; no image bodies.
- `resolution_client.py`: schema-checked, read-only HTTP status with timeout/failure handling.
- `server.py`: loopback v1 API and synthetic browser endpoints with server-held demo context; opt-in `--extractor omniroute --omniroute-env PATH --model MODEL`.
- `../ai/omniroute.py`: supervised local-gateway image calls, bounded responses, sanitized diagnostics, no client retries or fixture fallback.

No imports from the other service, no cross-database access and no refund tools. v1 is internal and currently unauthenticated; synthetic use only.
