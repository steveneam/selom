# Nango (self-hosted) — Selom's OAuth broker for cloud-storage imports

Nango holds the OAuth tokens for the cloud providers (Google Drive / OneDrive / Dropbox); Selom's
backend asks Nango for a live access token and streams the file into the intake pipeline. The
URL/S3 import path needs no OAuth and works without any provider setup.

## Run

```bash
cp .env.example .env          # then fill NANGO_ENCRYPTION_KEY (openssl rand -base64 32) + passwords
sudo docker compose up -d
curl -fsS http://localhost:3003/health        # -> {"result":"ok"}
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
origin before going live, then register that `…/oauth/callback` in each provider's app console
(Google Cloud, Azure AD, Dropbox). Add each integration in the Nango dashboard with its client
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
