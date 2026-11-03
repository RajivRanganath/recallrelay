# Evidence lane

Implementation space for this lane's backend, AI adapter, UI, tests and evaluation.

This folder currently contains no live implementation. Run `python3 -m unittest discover -s evidence/tests -v` from the repo root for the starter contract check. See docs/START-RAJIV.md for ownership and first tasks.

Recommended layout: `backend/`, `ai/`, `web/`, `tests/`, `evals/`. Own dependency and lock files here. Both lanes can use Python backends and plain HTML/JS initially; no shared framework choice is required. Before selecting a live model provider, confirm credentials and costs with the account owner. All initial development works against mocks.
