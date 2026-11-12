# Working on RecallRelay

One project, two contributors: [RajivRanganath](https://github.com/RajivRanganath) and [VismayaM2005](https://github.com/VismayaM2005).

## Structure
- `evidence/`: customer side. Label reading, campaign assessment, the unified workspace and its gateway.
- `resolution/`: merchant side. Case review, approval, PayPal refunds and webhooks.
- `contracts/`: the v1 JSON contract between the two services, with schemas, fixtures and mocks in `scripts/`.
- `docs/`: guides and measured results. `docs/process/` and `docs/evidence/history/` are dated records, kept as written.

The services talk only over HTTP. Each keeps its own storage and dependency files; neither imports the other or opens its database. No root runtime dependencies. Match the v1 contract and do not rename fields casually. A contract change goes in its own PR; a v2 would live beside v1 until both services migrate.

## Branches and PRs
No direct feature commits to main. Use short feature branches and small PRs, and review one another's work. Talk to the other contributor before changing code they wrote. Develop and test against fixtures and the committed mocks first; nobody waits for a real provider.

## Boundaries
All examples are synthetic. No live payments, real customer outreach, public deployment or credentials in commits. AI proposes extracted information and prose; deterministic code and human approval control eligibility and refunds. Do not treat untrusted images or case notes as instructions. Never log full uploaded images or secrets. Keep uncertainty visible.

No accuracy, user savings, production readiness or exactly-once guarantees without measured evidence. Record actual test scope, failures and provider mode.
