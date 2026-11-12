# Start here: RajivRanganath

Current implementation: use the [repository quick start](../../README.md#run-both-apps) and [integrated runbook](../evidence/history/FINAL-INTEGRATION.md) to run the implemented customer and merchant apps. Issues #1–#5 are closed; the instructions below preserve the original independent scaffold workflow and lane boundaries.

You own `evidence/`, `docs/rajiv/`, and `.github/workflows/evidence.yml`. Your slice includes AI, backend, UI and testing. See [task board](TASKS.md) for the equal 20-point split.

```sh
git clone https://github.com/RajivRanganath/recallrelay.git
cd recallrelay
git switch work/rajiv-evidence
python3 scripts/mock_server.py resolution --port 8102
```

In a second terminal run your lane's commands as you implement them. Read `evidence/README.md` and `contracts/README.md` first. No real AI or payment credentials are needed for the scaffold. Choose your own lane dependencies; record them only in your lane. Do not modify the other lane's files.

Start with task 1's deterministic mock path and task 3's basic UI, then implement your backend and AI. Mock-first is not a completion claim: actual provider behavior must be separately verified.

Create small feature branches from your starting branch (for example `work/rajiv-evidence-intake`), open PRs to `main`, and request the other contributor's review. Rebase/merge main into your branch before integration. Do not overwrite the other contributor's branch.

Your counterpart can start without you: preserve the contract and exercise their mock. If an API change is needed, propose v2 in a dedicated PR while continuing against v1.
