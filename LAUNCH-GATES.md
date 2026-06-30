# Launch gates — DEFERRED commercial checklist

> **Status: INTENTIONALLY DEFERRED.** Per the owner, Selom is being built
> **for-self first**. These commercial/licensing gates **must NOT block any
> build work**. They are the checklist to **re-apply BEFORE any public launch**
> (the moment Selom is served to third parties or charged for). Build now; gate
> before launch.

## Why deferred (not skipped)

Gating now would stall a single-user build for compliance that only bites at
public-serve time. So we record the gates here, keep building, and run this list
as a launch precondition. Nothing below is a backend blocker today.

## Gate checklist — re-apply before public launch

### 1. License / SCA scan (AGPL + non-commercial quarantine)
- Run a software-composition-analysis (SCA) scan across all backend deps.
- **Quarantine AGPL / non-commercial-restricted packages** off the hot path.
  Known watch items: **`gseapy`** and **MSigDB** gene-set data (license terms
  restrict redistribution / commercial use — confirm before shipping them in a
  paid path; isolate or replace if non-commercial-only).
- Output: a dependency license inventory with each package marked
  ship-clean / quarantine / replace.
- **LLM model license (AI gateway).** The live `gateway` path
  (`SELOM_AI_GATEWAY=gateway`) ships with whatever `ai_gateway_model` is set —
  default **`meta/llama-3.3-70b`**. The model is reached arms-length over the
  Vercel AI Gateway (HTTP), so there is **no GPL/AGPL on the Python path** — but
  the *model's own* license still binds a product that surfaces its outputs.
  Llama 3.3 (Community License) requires a prominent **"Built with Llama"**
  attribution + naming constraints (the 700M-MAU clause does not apply here).
  Before public launch: **verify the CURRENT license of whichever model
  `ai_gateway_model` actually ships with** and satisfy its terms, **or** ship a
  model whose terms are already met. Provider-agnostic (one-string swap), so this
  is a launch-time check, not a code blocker now. (`docs/ai-gateway-wiring/spec.md`.)

### 2. Billing — merchant-of-record vs raw Stripe
- Default to a **merchant-of-record** (e.g. **Lemon Squeezy** or **Paddle**) so
  they handle global sales tax / VAT remittance, rather than raw **Stripe**
  (where Selom owns all tax compliance itself).
- Decide MoR vs Stripe before charging the first external customer.

### 3. Terms of service / data warranty
- **Research-use-only ToS** (Selom outputs are not clinical/diagnostic).
- **De-identification warranty:** users assert uploaded omics data is
  de-identified; no PHI on the platform.
- Surface both at signup and upload.

### 4. Skill provenance / license metadata
- Every skill carries **license + provenance metadata** (which library/method it
  wraps, under what license, citation). Block any skill whose underlying method
  is non-commercial-only from the paid tier; expose provenance to users.

## Owner directive (binding)

These gates are deferred by explicit owner choice for the build-for-self phase.
Do **not** let any of them block backend or frontend work. Re-open this file and
clear every item before the first public launch.
