#!/usr/bin/env bash
# Nango deploy preflight — exit-code gated. Run after ANY change to the proxy, the hostname or
# deploy/nango/.env, and before asking a human to complete an OAuth consent.
#
#   bash deploy/nango/preflight.sh
#
# It exists because of one real failure (2026-07-25): the stack was stood up on localhost, a public
# hostname was put in front of it later, and NANGO_SERVER_URL was never updated. The authorize step
# still sent the correct redirect_uri (Nango derives that from the forwarded host), so the consent
# screen looked perfect — then the code EXCHANGE re-derived the callback from NANGO_SERVER_URL and
# Google rejected it as redirect_uri_mismatch. Symptom: a user who consents, and zero connections.
# Checks 3 + 4 below are the ones that catch it.
set -uo pipefail

CONTAINER=selom-nango-server
BACKEND_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/app/backend/.env"
fails=0
ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; fails=$((fails + 1)); }

DOCKER=docker
docker ps >/dev/null 2>&1 || DOCKER="sudo docker"

# The public origin Selom itself talks to is the source of truth for what "public" means.
# An exported SELOM_NANGO_BASE_URL wins, so the failure path can be exercised without editing .env.
BASE="${SELOM_NANGO_BASE_URL:-$(grep -E '^SELOM_NANGO_BASE_URL=' "$BACKEND_ENV" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"' \r')}"
[ -n "$BASE" ] || { echo "preflight: SELOM_NANGO_BASE_URL missing from $BACKEND_ENV"; exit 2; }
echo "Nango preflight — public origin: $BASE"

# 1. the container is up
if [ "$($DOCKER inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
  ok "$CONTAINER is running"
else
  fail "$CONTAINER is not running"
fi

# 2. the public origin answers (proves the proxy + TLS, not just the loopback bind)
code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$BASE/health" 2>/dev/null)
[ "$code" = "200" ] && ok "GET $BASE/health -> 200" || fail "GET $BASE/health -> ${code:-no response}"

# 3. the server's OWN idea of its origin matches the public one (the 2026-07-25 bug)
env_out=$($DOCKER exec "$CONTAINER" env 2>/dev/null)
for var in NANGO_SERVER_URL NANGO_PUBLIC_SERVER_URL; do
  val=$(printf '%s\n' "$env_out" | grep -E "^$var=" | cut -d= -f2- | sed 's:/*$::')
  if [ "$val" = "${BASE%/}" ]; then
    ok "$var = $val"
  else
    fail "$var = ${val:-<unset>} (must be ${BASE%/} — a stale value fails the code exchange AFTER consent)"
  fi
done

# 4. the callback the server prints at boot is the public one providers have registered
banner=$($DOCKER logs "$CONTAINER" 2>&1 | grep -o 'OAuth callback URL: [^ ]*' | tail -1 | awk '{print $NF}')
[ "$banner" = "${BASE%/}/oauth/callback" ] \
  && ok "boot banner callback = $banner" \
  || fail "boot banner callback = ${banner:-<none>} (expected ${BASE%/}/oauth/callback)"

echo
[ "$fails" -eq 0 ] && { echo "preflight PASSED"; exit 0; }
echo "preflight FAILED — $fails check(s). Fix deploy/nango/.env, then: sudo docker compose up -d nango-server"
exit 1
