#!/usr/bin/env bash
# HTTP semantic smoke test for the harness `apiVerify` step.
# Boots the API on an ephemeral port, verifies GET /orders/1/total returns
# 200 with the expected body, then shuts the app down. Exits non-zero on
# any failure so the harness treats it as a failing check.
set -euo pipefail

PORT=5199
BASE="http://127.0.0.1:${PORT}"
DOTNET="${DOTNET:-$HOME/.dotnet/dotnet}"

cd "$(dirname "$0")/.."

"$DOTNET" run --project src/OrdersApi/OrdersApi.csproj --urls "$BASE" >/tmp/ordersapi-smoke.log 2>&1 &
APP_PID=$!

cleanup() { kill "$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Wait for the app to accept connections (max ~20s).
for _ in $(seq 1 40); do
  if curl -fsS "${BASE}/orders/1/total" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

STATUS=$(curl -s -o /tmp/ordersapi-body.txt -w "%{http_code}" "${BASE}/orders/1/total")
BODY=$(cat /tmp/ordersapi-body.txt)

if [ "$STATUS" != "200" ]; then
  echo "api-smoke FAIL: GET /orders/1/total returned HTTP $STATUS (expected 200)"
  exit 1
fi

if [ "$(echo "$BODY" | tr -d '[:space:]')" != "50" ]; then
  echo "api-smoke FAIL: body was '$BODY' (expected 50)"
  exit 1
fi

echo "api-smoke PASS: GET /orders/1/total -> 200, body=50"
