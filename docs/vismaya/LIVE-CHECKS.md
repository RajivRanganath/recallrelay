# Live checks (you run these; credentials never go through Claude or into git)

Two pieces were built and tested against stubs. The **PayPal sandbox refund (check 2) has been run and verified once, on 9 November 2026**; see the runbook. The **real AI brief evaluation (check 1) was run four times on 9 November 2026** against `gemini-3.1-flash-lite` through the direct Gemini API: 10, 10, 12 and 12 of 14 briefs came from the model and the rest fell back to the template, with the checker changed between runs and then frozen for the last one (case names, reasons and limits are in the runbook). The app itself has not yet been run with `--brief gemini` against Google. An OmniRoute gateway was started in Docker that day, but its dashboard setup failed at the provider step ("Invalid provider") before any model call, so OmniRoute was never used. In the demo, describe the brief as "AI-drafted when it passes our checks, template otherwise", and only after you have seen it work in the app.

## Keep secrets safe

- Put each env file **outside the repository**, for example `C:\Users\VISMAYA\secrets\paypal.env` and `C:\Users\VISMAYA\secrets\gemini.env`. (`resolution/.gitignore` also ignores `*.env` and `.env*` inside the lane.)
- Each file holds plain `NAME=value` lines. Nothing is executed.
- Use **sandbox** PayPal credentials only. Never paste a secret into chat, a commit or a screenshot.

`paypal.env`:
```
PAYPAL_CLIENT_ID=your-sandbox-client-id
PAYPAL_CLIENT_SECRET=your-sandbox-client-secret
```
`gemini.env`:
```
GEMINI_API_KEY=your-google-ai-studio-key
```

## 1. Real AI brief evaluation (direct Gemini, no gateway needed)

1. Create a key at https://aistudio.google.com/apikey and save it in `C:\Users\VISMAYA\secrets\gemini.env` as shown above. Free-tier keys can use inputs to improve Google's products; the evaluation cases are invented, so that is fine, but never send real customer data.
2. List the models your key can call (the key is read into a variable and never printed). In PowerShell:
   ```
   $k = (Select-String -Path C:\Users\VISMAYA\secrets\gemini.env -Pattern '^GEMINI_API_KEY=(.*)$').Matches.Groups[1].Value
   (Invoke-RestMethod "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100" -Headers @{"x-goog-api-key"=$k}).models | Where-Object { $_.supportedGenerationMethods -contains "generateContent" } | ForEach-Object { $_.name }
   ```
   Pick a fast text model and drop the `models/` prefix from its name, for example `gemini-xxx-flash`. Use a name that is actually printed; model names change over time.
3. Run the evaluation with a **new** report name:
   ```
   cd C:\Users\VISMAYA\Desktop\paypal\recallrelay
   python -m resolution.evals.run --provider gemini --gemini-env C:\Users\VISMAYA\secrets\gemini.env --gemini-model MODEL_NAME --output resolution/evals/reports/gemini-first-run.json
   ```
4. Read the printed table. `provider_with_validation` shows how many of the 14 briefs came from the AI (`briefs_from_ai`), how many fell back to the template and why (`fallback_reason`: `invalid_output` means the draft failed the checks; `http_429` is a quota limit; `http_400` often means a bad key or model name), and which checks failed on which cases. Report those numbers exactly, including failures.
5. To use it in the app:
   ```
   python -m resolution.backend.server --brief gemini --gemini-env C:\Users\VISMAYA\secrets\gemini.env --gemini-model MODEL_NAME
   ```
   The first line must end with `brief: AI via gemini (validated)`.

Not verified: the adapter has only run against a local stub of Google's API, so the first real call may need a small fix. If every brief falls back with `http_400` or `invalid_response`, tell Claude the code (not the key).

(An OmniRoute option also exists, `--provider omniroute`, but it needs a configured local gateway and was not completed.)

## 2. Real PayPal sandbox refund (done once on 9 November 2026)

One-time setup in the PayPal Developer dashboard (sandbox): create an app to get the client ID and secret, and have one sandbox **business** account (receives money) and one sandbox **personal** account (the buyer).

1. Create a real sandbox payment and a case that points at it. A browser link appears; open it, log in as the **sandbox buyer** and approve. Check the address starts with `https://www.sandbox.paypal.com/`. Then press Enter in the terminal.
   ```
   python -m resolution.sandbox.make_capture --paypal-env C:\Users\VISMAYA\secrets\paypal.env --output resolution/.local/sandbox-case-NEW.json
   ```
   The case file is git-ignored. The assessment inside it is the synthetic fixture, not a real evidence result. Use a new `--output` name each time; the script never overwrites.
2. Start the server in sandbox mode. The first line must say `PayPal SANDBOX refunds (no live money)`:
   ```
   python -m resolution.backend.server --paypal sandbox --paypal-env C:\Users\VISMAYA\secrets\paypal.env
   ```
3. Load the case from a second terminal (`curl.exe`, not `curl`):
   ```
   curl.exe -X POST http://127.0.0.1:8102/v1/resolutions -H "Content-Type: application/json" --data-binary "@resolution/.local/sandbox-case-NEW.json"
   ```
4. In the browser open http://127.0.0.1:8102, select `case-sandbox-1`, confirm the remedy and approve the exact amount. The result should say **PayPal sandbox** and show a real refund ID.
5. Prove it from PayPal's side (read-only), using the real refund ID shown in the app:
   ```
   python -m resolution.sandbox.verify_refund REFUND_ID --paypal-env C:\Users\VISMAYA\secrets\paypal.env
   ```
   It should print `status: COMPLETED` and the amount. Only then call the sandbox refund verified.

If the refund comes back `pending`, PayPal answered with something unexpected or the network failed. Use **Check refund again** (same operation ID, so no duplicate), then verify.

## What to write down

Date, what you ran, the exact printed numbers or IDs, and anything that failed. Do not claim more than what printed.
