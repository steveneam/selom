# Nango (self-hosted) — Selom's OAuth broker for cloud-storage imports

Nango holds the OAuth tokens for the cloud providers (Google Drive / OneDrive / Dropbox); Selom's
backend asks Nango for a live access token and streams the file into the intake pipeline. The
URL/S3 import path needs no OAuth and works without any provider setup.

## Run

> **This stack is STOPPED as of 2026-07-25** (owner-approved cleanup). It is the syd4 **dev copy** and
> nothing uses it — Selom's backend talks to swordfish's live broker on syd2. Its containers and
> volumes are intact; restart with `sudo docker compose -f deploy/nango/docker-compose.yaml start`
> (~500 MB on a shared box, so only start it when you actually need a local broker). With it down,
> `preflight.sh` correctly reports `SKIP no local selom-nango-server` and still verifies the live
> instance — a skip, not a pass.

```bash
cp .env.example .env          # then fill NANGO_ENCRYPTION_KEY (openssl rand -base64 32) + passwords
sudo docker compose up -d
curl -fsS http://localhost:3003/health        # -> {"result":"ok"}
bash preflight.sh                             # exit-code gated; run after ANY proxy/hostname change
```

Everything binds to `127.0.0.1` only — a reverse proxy is what exposes it publicly.

## Ports (host)

| Service            | Host port | Notes                                         |
|--------------------|-----------|-----------------------------------------------|
| Nango server / API | `3003`    | dashboard + REST API + `/health`              |
| Connect UI         | `3009`    | the hosted OAuth connect popup                |
| Postgres (Nango)   | `5433`    | Nango's own DB (host `:5432` is taken)        |
| Redis (Nango)      | `6380`    | remapped off `:6379`                          |

## OAuth callback URL (register this with each provider app)

Nango builds the callback from `NANGO_SERVER_URL`:

- **Dev (this box):** `http://localhost:3003/oauth/callback`
- **Production (behind a reverse proxy):** `https://<nango-public-domain>/oauth/callback`

Set `NANGO_SERVER_URL` (and `NANGO_PUBLIC_SERVER_URL` / `NANGO_PUBLIC_CONNECT_URL`) to the public
origin **the moment a proxy lands in front of the stack**, recreate the server, and register that
`…/oauth/callback` in each provider's app console (Google Cloud, Azure AD, Dropbox).

> **TWO INSTANCES — read this before diagnosing anything (2026-07-25).**
> - **LIVE:** `https://nango.swordfish.cfd`, swordfish-provisioned **on syd2**. Holds the real
>   integrations and the owner's connections; `SELOM_NANGO_BASE_URL` points here.
> - **DEV:** this compose stack, `127.0.0.1:3003` on **syd4** — a separate instance with its own
>   Postgres and its own secret key. It shares nothing with the live one.
>
> Confusing them cost a diagnosis: a stale `localhost` origin was found and "fixed" on the dev copy
> and reported as the cause of a live OAuth failure. The tell is one command —
> Selom's secret key returns `unknown_account` on the instance it doesn't belong to. That is
> `preflight.sh` check 2; the container-level checks **skip** unless the key authenticates both at
> `BASE` and on the local container's own port, because a container's `NANGO_SERVER_URL` is a *claim*.
>
> The stale-origin hazard is still real, just not what happened here: with a proxy in front, authorize
> derives `redirect_uri` from the forwarded host and the consent screen looks perfect, then the code
> **exchange** re-derives the callback from `NANGO_SERVER_URL` and the provider rejects it — breaking
> *after* a human consents, with no connection persisted. Run `bash preflight.sh [BASE]` before asking
> anyone to complete a consent. Add each integration in the Nango dashboard with its client
id/secret; its integration id must match the `provider_config_key` in the backend registry
(`app/backend/cloud/registry.py`): `google-drive`, `onedrive`, `dropbox`.

## Wiring Selom to Nango

Set these on the Selom backend (they default to off/empty, so nothing changes until you do):

```
SELOM_NANGO_BASE_URL=http://localhost:3003
SELOM_NANGO_SECRET_KEY=<Nango secret key from the dashboard>
SELOM_CLOUD_GOOGLE=true         # flip per provider once its client ids exist in Nango
SELOM_CLOUD_ONEDRIVE=true
SELOM_CLOUD_DROPBOX=true
```

## Security

`.env` (secrets) and `nango-data/` (Postgres volume) are gitignored. Rotating
`NANGO_ENCRYPTION_KEY` after data exists breaks decryption — set it once per environment. Pin the
`nangohq/nango-server` image to a version/commit-hash tag before production.
