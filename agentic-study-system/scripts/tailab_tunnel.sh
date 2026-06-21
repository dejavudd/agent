#!/usr/bin/env bash
# Open an SSH tunnel to the tailab vLLM (gpt-oss) server and keep it alive.
#
# The vLLM container publishes its OpenAI-compatible API on the tailab *host*
# port 8006 (container port 8000), which is NOT exposed to the internet — only
# SSH (port 52345) is. This script forwards localhost:8006 -> tailab:8006 so the
# Agentic Study app (API_PROVIDER=vllm, VLLM_BASE_URL=http://localhost:8006/v1)
# can reach it.
#
# Usage:
#   scripts/tailab_tunnel.sh           # start the container if needed, then tunnel
#   scripts/tailab_tunnel.sh --no-start  # just tunnel (assume container is up)
#
# Leave this running in its own terminal while you use the study system.
set -euo pipefail

HOST="${TAILAB_SSH_HOST:-tailab}"
LOCAL_PORT="${TAILAB_LOCAL_PORT:-8006}"
REMOTE_PORT="${TAILAB_REMOTE_PORT:-8006}"
CONTAINER="${TAILAB_CONTAINER:-vllm-gpt-oss-120b}"

if [[ "${1:-}" != "--no-start" ]]; then
  echo "→ Ensuring container '$CONTAINER' is running on $HOST..."
  ssh "$HOST" "docker start $CONTAINER >/dev/null && \
    docker ps --filter name=$CONTAINER --format '  {{.Names}}: {{.Status}}'"
fi

echo "→ Tunneling localhost:$LOCAL_PORT → $HOST:$REMOTE_PORT (Ctrl-C to stop)"
echo "  Test in another terminal:  curl -s http://localhost:$LOCAL_PORT/v1/models | head"
exec ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  -L "${LOCAL_PORT}:localhost:${REMOTE_PORT}" \
  "$HOST"
