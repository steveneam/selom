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
- **Nango — Elastic License 2.0 (non-OSI, source-available).** Verified at the
  source on 2026-07-25 (`github.com/NangoHQ/nango` `LICENSE`); the npm packages
  `@nangohq/frontend` / `@nangohq/types` (0.71.2) declare "SEE LICENSE IN LICENSE
  FILE IN GIT REPOSITORY" and ship no license file of their own, so the repo's
  ELv2 governs. Nango is on the shipped path in two places: the self-hosted
  broker (`deploy/nango/`, image `nangohq/nango-server`) and the FE dependency.
  **Assessment:** ELv2's operative restriction is *"You may not provide the
  software to third parties as a hosted or managed service, where the service
  provides users with access to any substantial set of the features or
  functionality of the software."* Selom uses Nango **internally**, as its own
  OAuth broker — users never get access to Nango's features, only to Selom's
  cloud-import. That is permitted. It becomes a **blocker** only if Selom ever
  exposes Nango itself (a connections dashboard, integration management, or the
  Connect UI as a product surface). Two obligations that bind regardless:
  **do not remove or obscure Nango's licensing/copyright notices**, and **do not
  circumvent any license-key functionality**. Before launch: re-verify the
  license (they have changed it before), confirm no Nango surface is exposed to
  users, and record ELv2 in the dependency inventory rather than letting an SCA
  scan flag it as an unknown-license surprise.
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
