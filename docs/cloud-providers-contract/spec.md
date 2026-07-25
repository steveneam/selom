# `GET /cloud/providers` — the frozen cross-lane contract

Status: **FROZEN** · 2026-07-25 · next-session-plan `P0-03`

## Why this contract exists

Google Drive and Dropbox are **connected and live** (real refresh tokens, live API calls returning
200), and the feature is still **unreachable in the product**. Three gates are closed, and one of
them is a fork: the FE keeps its own provider table (`lib/cloud/providers.ts`) with a hardcoded
`comingSoon: true`, because nothing ever tells it a provider became enabled. Review finding **A20**;
the pattern is [[selom-shipped-not-reachable]].

The fix is a single endpoint fed by the backend registry: **the server owns provider state, the FE
renders what it is told.** That deletes the second table rather than synchronising it.

## Where the contract actually lives

This document is the *weakest* expression of the contract and deliberately does not restate the
shape — per CLAUDE.md's ratchet ladder (executable > structural > config > documentary), the shape
lives in code that fails:

| Form | Location |
|---|---|
| **Executable freeze (authoritative)** | `app/backend/tests/test_contract_cloud_providers.py` |
| Backend declaration + serializer | `app/backend/cloud/contract.py` |
| Frontend declaration | `app/frontend/lib/cloud/contract.ts` |

Read `cloud/contract.py`'s module docstring for the shape and the reasoning behind each rule. If this
document and those files ever disagree, **the tests are right.**

## The five frozen rules

1. **Keys are exact** — exactly `PROVIDER_KEYS`, in that order, no more and no fewer.
2. **Order is part of the shape** — the list is the FE's menu order, server-owned; the client must
   not re-sort.
3. **`enabled` is the server's answer** — derived from `registry.is_enabled`, never a client guess.
   No client-side `comingSoon` may return.
4. **No credential material crosses the wire** — `provider_config_key` is a public Nango integration
   id, not a secret. Asserted independently.
5. **Unknown keys are additive-safe** — the FE maps what it knows and ignores the rest, so an
   additive backend field cannot break a deployed client.

## Why it is pinned on `main` before any lane forks

Lane 2 is the only implementer *and* the only consumer, but the freeze ships **before** it forks, on
purpose. Peer experience on this box says nearly every "lane collision" is **contract drift, not a
glob violation** — so a lane that improves the shared shape must go red **in its own run**, days
before the merge train sees it. Hand-resolving semantic drift at the train, under merge pressure, is
precisely how wrong code ships behind a green gate.

**The guard file sits outside Lane 2's owned glob.** Lane 2 owns `tests/test_cloud*.py`; the guard is
`test_contract_cloud_providers.py`. A lane editing its own freeze is therefore a visible scope breach
rather than a routine edit in its own territory.

## Changing this contract

A lane that needs a different shape does **not** widen the freeze. It stops and **re-plans** with the
founder — never a wave-through. Additive-only changes still update all three files listed above in
the **same commit**, including the FE declaration, so the cross-language guard never goes stale
([[mock-must-mirror-backend-contract]]).

## Implementation state

The shape, both declarations, and the guard are on `main`. The **route is not implemented** — that is
Lane 2's `L2-01`. The route-conformance test is dormant behind a skip that names `L2-01` and activates
automatically the moment the route is registered, with no further wiring. It asserts the *route's*
bytes, not just the serializer, so an endpoint that bypasses `providers_payload` and hand-rolls its
own dict is still caught.

Also still closed (both `L2-02`, and neither is a code change): `SELOM_CLOUD_GOOGLE` and
`SELOM_CLOUD_DROPBOX` are absent from `app/backend/.env`, so `enabled` will report `false` for both
until they are set — correctly, since the flags are what gate the OAuth path server-side.

## ⚑ Scope — Selom cannot see files the user already has (open founder decision, 2026-07-25)

Measured against the live broker while verifying `V-2`. **Both providers are sandboxed to files
Selom itself created**, so an account full of the user's own data looks empty to us:

| provider | granted access | what Selom can read |
|---|---|---|
| Google Drive | scope **`drive.file`** | only files the app **created**, or that the user picked through Google's own Picker |
| Dropbox | **App Folder** | only Selom's own folder — its visible root held exactly the one file we had just written |

**This makes the shipped affordance impossible to follow.** `cloud-import-menu.tsx` tells the user:
*"Open the file in Drive → Share → Copy link; the id is the `/d/<id>/` segment."* Under `drive.file`
that id names a file Selom has no permission to read, so the import cannot succeed — the instruction
describes a flow the grant forbids. Owner-raised the same day: *"not all files brought on by the user
will be originally created by Selom"*. Exactly so, and it is the normal case.

Compounding it: **`POST /export/cloud` is a stub for both OAuth providers** — `push_from_store`
raises "export is not available yet" in `cloud/connectors/google.py` and `cloud/connectors/dropbox.py`
(only the URL/S3 destination works). So the natural workaround — export a dataset to the account,
which Selom would then own and be able to read back — is not available either.

### The options, and the trade that decides it

1. **Google Picker (recommended).** The designed companion to `drive.file`: the user chooses the file
   in Google's own dialog, which grants the app access to *that* file. Keeps least-privilege, and it
   is the flow Google intends. Cost: a Picker integration in the FE plus an API key, and a Dropbox
   Chooser for parity.
2. **Broaden the scopes** — `drive.readonly` and full-Dropbox. The pasted-id flow starts working with
   no FE work. But `drive.readonly` is a Google **restricted** scope: production use requires a
   third-party CASA security assessment, renewed annually, at real cost — and it asks the user for
   their entire Drive to read one CSV.
3. **Implement export first**, then lean on export→re-import. Narrow, and it only helps data that
   originated in Selom — it does not solve bringing a user's existing file in, which is the point.

**Recommendation: (1).** It is the only option that both works for a file Selom did not create and
keeps the consent proportionate; (2) trades a launch gate and a much larger privacy ask for saved
build time. Either way this is a founder decision, not a lane call — it changes what users must
consent to.

_Verified 2026-07-25 against `nango.swordfish.cfd`: both connections refresh, `/cloud/connections`
returns both accounts, and a real CSV imported end-to-end from each provider once a file the app
owned was present. The limitation is the grant, not the plumbing._
