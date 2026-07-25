#!/usr/bin/env bash
# Nango preflight — exit-code gated. Run before asking a human to complete an OAuth consent, and
# after any change to the broker, its proxy or its hostname.
#
#   bash deploy/nango/preflight.sh [BASE_URL]
#
# TWO INSTANCES EXIST, and confusing them cost a diagnosis (2026-07-25):
#   - LIVE:  https://nango.swordfish.cfd — swordfish-provisioned, on **syd2**. Holds the real
#            integrations + the owner's connections. Selom's backend talks to this one.
#   - DEV:   127.0.0.1:3003 on syd4 (deploy/nango/docker-compose.yaml) — a separate stack with its
#            own DB and its own secret key. It shares NOTHING with the live one.
# Check 2 (the secret key authenticates at BASE) is what makes the distinction impossible to miss:
# a key from one instance returns `unknown_account` on the other.
#
# The container checks only run when BASE is actually served by a container on THIS box. For the live
# instance they SKIP — a skip is not a pass; its env must be verified where it runs (syd2/swordfish).
set -uo pipefail

CONTAINER=selom-nango-server
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The env file the BACKEND actually loads (app/backend/config.py: pydantic-settings
# env_file = <repo root>/.env). It used to read app/backend/.env, which the backend never loads —
# so this script could pass against the live broker while the server itself was still pointed at the
# dead 127.0.0.1:3003 default. One home per setting; locked by
# app/backend/tests/test_cloud_env_home.py.
BACKEND_ENV="$REPO_ROOT/.env"
fails=0; skips=0
ok()   { printf '  ok   %s\n' "$1"; }
skip() { printf '  SKIP %s\n' "$1"; skips=$((skips + 1)); }
fail() { printf '  FAIL %s\n' "$1"; fails=$((fails + 1)); }

DOCKER=docker
docker ps >/dev/null 2>&1 || DOCKER="sudo docker"

envval() { grep -E "^$1=" "$BACKEND_ENV" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"' \r'; }

# BASE = the instance under test. Positional arg wins, then an exported override, then the origin
# Selom's backend is actually configured to talk to.
BASE="${1:-${SELOM_NANGO_BASE_URL:-$(envval SELOM_NANGO_BASE_URL)}}"
BASE="${BASE%/}"
KEY="$(envval SELOM_NANGO_SECRET_KEY)"
[ -n "$BASE" ] || { echo "preflight: no base URL (arg, \$SELOM_NANGO_BASE_URL, or $BACKEND_ENV)"; exit 2; }
echo "Nango preflight — instance under test: $BASE"

# 1. the origin answers (proves proxy + TLS for a public host, not just a loopback bind)
code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$BASE/health" 2>/dev/null)
[ "$code" = "200" ] && ok "GET $BASE/health -> 200" || fail "GET $BASE/health -> ${code:-no response}"

# 2. IDENTITY — the secret key Selom uses belongs to the instance at BASE (catches instance mixups)
if [ -z "$KEY" ]; then
  fail "SELOM_NANGO_SECRET_KEY missing from $BACKEND_ENV"
else
  body=$(curl -s -m 15 -H "Authorization: Bearer $KEY" "$BASE/integrations" 2>/dev/null)
  case "$body" in
    *unknown_account*|*'Authentication failed'*)
      fail "the secret key is NOT valid at $BASE (unknown_account) — wrong instance or wrong key" ;;
    *'"data"'*)
      n=$(printf '%s' "$body" | grep -o '"unique_key"' | wc -l | tr -d ' ')
      ok "secret key authenticates at $BASE; $n integration(s) configured" ;;
    *) fail "unexpected /integrations response from $BASE: $(printf '%s' "$body" | head -c 120)" ;;
  esac
fi

# 3+4. Container-level checks — ONLY meaningful when the container on this box IS the instance at
# BASE. Do not trust the container's own NANGO_SERVER_URL for that (it is a claim, and a wrong claim
# is exactly the bug being hunted). Bind by evidence: the key that authenticates at BASE must also
# authenticate against the container's own port. Different DB -> unknown_account -> different instance.
is_local_instance=no
if [ "$($DOCKER inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ] && [ -n "$KEY" ]; then
  lport=$($DOCKER exec "$CONTAINER" env 2>/dev/null | grep -E '^SERVER_PORT=' | cut -d= -f2-)
  lbody=$(curl -s -m 10 -H "Authorization: Bearer $KEY" "http://localhost:${lport:-3003}/integrations" 2>/dev/null)
  case "$lbody" in *'"data"'*) is_local_instance=yes ;; esac
fi
if [ "$($DOCKER inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != "true" ]; then
  skip "no local $CONTAINER — nothing on this box to inspect"
elif [ "$is_local_instance" != "yes" ]; then
  skip "cannot bind this box's $CONTAINER to $BASE (the key does not authenticate on both) — treat"
  skip "them as separate stacks; verify $BASE's own NANGO_SERVER_URL + boot banner where it runs."
else
  env_out=$($DOCKER exec "$CONTAINER" env 2>/dev/null)
  for var in NANGO_SERVER_URL NANGO_PUBLIC_SERVER_URL; do
    val=$(printf '%s\n' "$env_out" | grep -E "^$var=" | cut -d= -f2- | sed 's:/*$::')
    [ "$val" = "$BASE" ] && ok "$var = $val" \
      || fail "$var = ${val:-<unset>} (must be $BASE — a stale value fails the code exchange AFTER consent)"
  done
  banner=$($DOCKER logs "$CONTAINER" 2>&1 | grep -o 'OAuth callback URL: [^ ]*' | tail -1 | awk '{print $NF}')
  [ "$banner" = "$BASE/oauth/callback" ] && ok "boot banner callback = $banner" \
    || fail "boot banner callback = ${banner:-<none>} (expected $BASE/oauth/callback)"
fi

# 5. Existing connections still refresh (the only end-to-end proof the broker works)
if [ -n "$KEY" ]; then
  conns=$(curl -s -m 15 -H "Authorization: Bearer $KEY" "$BASE/connections" 2>/dev/null)
  ids=$(printf '%s' "$conns" | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for c in d.get('connections',[]) or []:
    print(c.get('connection_id',''), c.get('provider_config_key',''))
" 2>/dev/null)
  if [ -z "$ids" ]; then
    skip "no connections yet at $BASE — nothing to refresh-test"
  else
    while read -r cid pck; do
      [ -n "$cid" ] || continue
      r=$(curl -s -m 25 -H "Authorization: Bearer $KEY" \
        "$BASE/connection/$cid?provider_config_key=$pck&refresh_token=true" 2>/dev/null)
      case "$r" in
        *'"access_token"'*) ok "$pck connection refreshes (${cid%%-*}…)" ;;
        *) fail "$pck connection $cid failed to refresh: $(printf '%s' "$r" | head -c 140)" ;;
      esac
    done <<< "$ids"
  fi
fi

echo
[ "$fails" -eq 0 ] && { echo "preflight PASSED${skips:+ ($skips skipped — a skip is not a pass)}"; exit 0; }
echo "preflight FAILED — $fails check(s), $skips skipped."
exit 1
