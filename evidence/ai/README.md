# Label extraction boundary — fixture mode

`extraction.LabelExtractor` is a provider-neutral interface. It receives only a decoded synthetic image and returns untrusted structured field data. It has no campaign/order/approval input, database handle, assessment function or payment tools. No live implementation or API keys are configured.

The lane-local output schema requires model and batch objects, each containing `value`, `confidence` and `uncertain`, with no extra fields. The server rejects malformed output, non-finite confidence and injected approval/tool-call fields. `normalize_proposal` suppresses missing, explicitly uncertain, ambiguous and below-threshold fields, then asks one deterministic clarification. The 0.85 threshold is a conservative test policy, **not calibrated confidence**. Suggestions do not create assessments; separate human confirmation and deterministic checks remain mandatory.

`FixtureExtractor` recognizes exact SHA-256 image bytes from the versioned synthetic manifest and returns authored outputs, always `mode: mock`. It is not OCR and cannot read arbitrary photos. An unknown image or adapter failure returns a sanitized unavailable error; typed entry stays available. Errors and representations do not include image bodies or provider exceptions.

`mock_extractor.propose(sample_id)` retains the three original sample controls and uses the same normalizer. Returned lists/maps are independent per call.

Next: select a live provider with account-owner consent, implement bounded provider timeouts and the same output boundary, then evaluate actual outputs against the frozen image set and typed-entry baseline. The current offline instruction-bearing cases do not establish a model's prompt-injection resistance. See [evaluation scope](../evals/README.md).
