# Frozen MVP scope

Customer: a fictional direct-to-consumer brand conducting an already approved refund recall. The brand funds refunds from its own PayPal account. The tool does not determine legal obligations or start a real recall.

The campaign is entered as structured, human-approved rules. Public CPSC notice ingestion is optional later; it is not the AI centerpiece. One campaign, one purchased unit per case, USD. A known order and capture anchor identity; authentication and upload authorization must be built before accepting any real data.

Rajiv's AI reads labels and proposes the smallest useful clarification. It cannot prove authenticity or ownership. Code evaluates confirmed identifiers against explicit rules. Missing or uncertain input remains `needs_information`. Excluded means excluded from this campaign, never safe.

Vismaya's AI writes a source-linked merchant brief and explains missing steps. It cannot approve or execute money. Human approval binds a verified assessment, amount, capture and campaign version. The executor checks current state and persists a stable operation ID before calling PayPal. Unknown responses stay pending until reconciled.

## Exclusions
No real customer data/messages; no live-money mode; no fraud/tampering detector; no older-purchase payouts; no multi-merchant onboarding; no CPSC crawler; no automated legal decisions; no marketplace; no production auth claim. Older purchases, open disputes or unsatisfied remedy conditions require manual handling.

## Success evidence
Compare label-assistant completion and errors with a typed-label form on identical synthetic cases. Merchant briefs must cite only supplied records and abstain on missing facts. Refund tests cover partial prior refunds, repeated events, concurrent requests, lost responses and failures. Report denominators and failures; no invented accuracy or savings.

## Demo allocation
Rajiv owns the first 75 seconds: upload -> extraction -> correction -> assessment.
Vismaya owns the next 75 seconds: grounded brief -> human approval -> sandbox refund -> replay/status.
Both rehearse transitions. Show labels for mock, AI and PayPal sandbox separately.
