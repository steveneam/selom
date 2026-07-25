# Nango (self-hosted) — Selom's OAuth broker for cloud-storage imports

Nango holds the OAuth tokens for the cloud providers (Google Drive / OneDrive / Dropbox); Selom's
backend asks Nango for a live access token and streams the file into the intake pipeline. The
URL/S3 import path needs no OAuth and works without any provider setup.

## Run

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

> **Landmine (cost a session, 2026-07-25).** A stale `localhost` value here does **not** fail loudly.
> The authorize step derives `redirect_uri` from the forwarded host, so the provider shows a perfect
> consent screen — then the code **exchange** re-derives the callback from `NANGO_SERVER_URL` and the
> provider rejects it (`redirect_uri_mismatch`). Symptom: a human who consents successfully, and
> `GET /connections` still empty. `preflight.sh` checks 3 + 4 exist to catch exactly this; run it
> before asking anyone to complete a consent. Add each integration in the Nango dashboard with its client
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
