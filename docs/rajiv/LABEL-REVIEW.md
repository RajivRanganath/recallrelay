# Offline development-reference review

The current twelve synthetic labels have already been inspected and used during provider tuning. This tool makes their authored references reviewable; it does not create a holdout or establish that a person reviewed them. No live provider, merchant service or payment is involved.

## Prepare a blank packet

From the repository root with the evidence Python 3.11 environment installed:

```sh
evidence/.venv/bin/python -B -m evidence.evals.review prepare --output evidence/.local/new-development-review
```

The destination must be a new directory. It contains `review.html`, a standalone form with embedded checked PNG/JPEG bytes, and `packet.json`, the manifest/image identity record. Open the HTML in a browser. The form requires no server or network connection; a local loopback server can also serve that directory. Keep the packet JSON with the form. Do not overwrite an earlier packet.

The page starts with blank fields and an unchecked reviewer declaration. It omits authored answers, semantic case IDs, mock proposals and provider output from its form data. Opaque sample IDs map back to the manifest only when checked. Image pixels can still contain identifying fixture text, so this is not a blinded experiment. The manifest hash includes the existing authored references even though those answers are not shown in the page.

## A person reviews the images

The reviewer enters a name or alias, inspects each image, and independently chooses one readable value, missing, unreadable/cut off, or conflicting values for both model and batch. A readable value must be transcribed; every other state stores null. Changing away from readable clears any stale value. Do not infer identifiers from product knowledge, instructions in the image, case names, generated source text, previous results or this repository's references. Optional notes should explain difficult choices.

The reviewer personally checks the declaration, then downloads the completed JSON record. The page does not upload or persist answers. Progress is kept only in the open tab; closing or reloading before download loses it. Choose an alias if the record should not contain a real name, and keep the downloaded record local until its contents have been reviewed for sharing.

An automated tool or agent must not complete that declaration as evidence of human work. Authored records used in unit tests are explicitly synthetic tooling checks and are never a completed review of this dataset. The generated packet remains blank for a person to fill.

## Check the returned record

Use the same frozen manifest and packet. This command accepts all cases exactly once, validates image and manifest hashes, readability/value consistency, reviewer declaration and the self-reported UTC timestamp. It does not authenticate the reviewer or timestamp, verify visual effort, or adjudicate truth.

```sh
evidence/.venv/bin/python -B -m evidence.evals.review check --packet evidence/.local/new-development-review/packet.json --review /absolute/path/to/downloaded-review.json --output evidence/.local/new-reference-audit.json
```

The output file must be new and its parent directory must exist. The report binds the packet and raw review hashes, preserves every compared value/readability choice and lists disagreements against the authored typed-entry reference. It does not change the manifest, application policy, evaluation plan or provider reports. It omits reviewer names/notes from the comparison report; preserve the original record separately when an audit trail is needed.

Exit codes: **0** means a structurally complete record agrees with every authored reference value; **1** means a complete report was saved/printed with one or more disagreements; **2** means input, drift, completeness or output-path checks failed. Disagreement does not mean the reviewer is wrong: either reference may need correction. Missing/unreadable/conflicting choices all compare as null while retaining the separate readability status. Readability classifications themselves have no authored scoring target here.

Packets and reports always retain `holdout: false` and `human_validated: false`. Reviewer identity and visual work remain self-reported. Hashes detect drift against supplied local files; they are not signatures, evidence of independent review, a trusted timestamp or proof that the exported page was untampered. Agreement alone cannot establish correct labels, extraction accuracy, calibrated confidence, human completion effort or user savings.

## Adjudication and a future holdout

Preserve disagreements and reviewer notes, inspect the images with a real reviewer, and document any agreed corrections in a new version rather than silently replacing existing references. A new synthetic v1 manifest can be selected with the same `--manifest PATH` during both preparation and checking; normal image/reference preflight still applies. Packets from this command remain development reference audits regardless of the chosen directory name.

A future holdout needs a separately recorded dataset/reviewer process, independent labels, a frozen protocol before provider exposure, documented tuning/visibility history, and explicit supported reporting. Do not relabel these twelve development images as unseen. Human timing/effort measurement is separate. The existing evaluator intentionally continues to reject plans that claim reviewed holdout or human validation without that protocol.

## Tool verification

Nine Python regressions cover blank answer-free packets and exact embedded bytes, self-reported records, disagreement preservation, coverage/schema/uncertainty, edited claims, dataset/packet drift, strict/oversized JSON, offline CLI behavior and overwrite protection. Three Node DOM-double checks exercise blank form values, state invalidation, export binding and invalid-form rejection. The rendered browser check covers blank/disabled initial fields, readable-field enabling, clearing a temporary UI-test value on uncertainty, and resetting to a fully blank packet. The reviewer declaration is left unchecked and no human review result is generated.
