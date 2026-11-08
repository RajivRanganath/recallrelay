# Blank human-evaluation templates

These CSVs contain headers only: no participants, measurements, adjudications or results. Copy them into a new ignored `evidence/.local/` directory and follow [the protocol](../../../docs/rajiv/HUMAN-EVALUATION.md). Keep raw downloaded image-review JSON and its packet together; these CSVs do not replace that checker format.

`sessions.csv` records session configuration and prior exposure. `trials.csv` records all actual attempts, including failures/timeouts; `adjudication.csv` records actual disagreements and decisions. Use anonymous aliases, synthetic image/case IDs and correct CSV quoting. Keep free-text private until reviewed. Do not commit filled records by default. Unknown measurements are blank with an explanatory note; `na` means not applicable. None of these templates authenticates identity, timestamps or human work.
