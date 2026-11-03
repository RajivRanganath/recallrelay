# Collaboration rules

## Exclusive lanes
- `evidence/**`, `docs/rajiv/**`, `.github/workflows/evidence.yml`: RajivRanganath only.
- `resolution/**`, `docs/vismaya/**`, `.github/workflows/resolution.yml`: VismayaM2005 only.
- `contracts/**`, `scripts/**`, `tests/**`, root config/docs and shared CI: frozen setup; changes require a dedicated contract/setup PR reviewed by the other contributor.

Do not edit the other person's files to unblock yourself. Use the committed mocks. No shared application database or ORM models. Each service owns its storage and dependency files. No root runtime dependencies.

Each person owns AI, backend, UI, tests, evaluation and docs in their lane. Match the frozen contract; do not rename fields casually. Future v2 additions live beside v1; v1 stays usable until both migrate. Requests need only one-way HTTP calls, never cross-database access.

## Branches and PRs
Use `work/rajiv-evidence` and `work/vismaya-resolution` as starting branches. Prefer short feature branches under your lane. No direct feature commits to main. A small PR should change one lane only. Review one another's PRs; ownership is routing, not a claim that branch protections are enabled.

Shared integration is divided in docs/TASKS.md. Nobody waits for a real provider: develop and test with fixtures first. If contract changes are proposed, continue on v1 until merged. Reserve a daily 15-minute integration check.

## Boundaries
All examples are synthetic. No live payments, real customer outreach, public deployment or credentials in commits. AI proposes extracted information and prose; deterministic code and human approval control eligibility and refunds. Do not treat untrusted images or case notes as instructions. Never log full uploaded images or secrets. Keep uncertainty visible.

No accuracy, user savings, production readiness or exactly-once guarantees without measured evidence. Record actual test scope, failures and provider mode. No AI provider is selected or wired in this scaffold.
