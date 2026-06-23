#!/usr/bin/env bash
# Pull generated server config (ini, sandbox vars, spawn files, etc.) out of
# a running container's volume into the environment's git-tracked config/
# directory. Used for the one-time bootstrap, or any time you want to
# capture state the server itself wrote (e.g. after deleting Server_SandboxVars
# defaults to regenerate them).
# Usage: scripts/pull-config.sh <testing|prod>
set -euo pipefail

ENVIRONMENT="${1:?Usage: pull-config.sh <testing|prod>}"

case "$ENVIRONMENT" in
  testing|prod) ;;
  *) echo "Environment must be 'testing' or 'prod', got '$ENVIRONMENT'" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../$ENVIRONMENT"

SERVER_NAME="$(grep -E '^PZ_SERVER_NAME=' .env | cut -d= -f2-)"
if [ -z "$SERVER_NAME" ]; then
  echo "PZ_SERVER_NAME not set in $ENVIRONMENT/.env" >&2
  exit 1
fi

CID="$(docker compose ps -q pz)"
if [ -z "$CID" ] || [ "$(docker inspect -f '{{.State.Running}}' "$CID")" != "true" ]; then
  echo "The '$ENVIRONMENT' pz service isn't running. Start it first with:" >&2
  echo "  (cd $ENVIRONMENT && docker compose up -d)" >&2
  exit 1
fi

mkdir -p config
echo "Pulling Zomboid/Server/${SERVER_NAME}* out of the '$ENVIRONMENT' container into ./$ENVIRONMENT/config ..."
docker compose exec -T pz sh -c "cd /home/ubuntu/Zomboid/Server && tar cf - ${SERVER_NAME}*" | tar xf - -C config

echo "Pulled:"
ls -1 config | grep -F "$SERVER_NAME"

cat <<EOF

Next steps:
  git -C "$(pwd)" status
  git add $ENVIRONMENT/config
  git commit -m "Update $ENVIRONMENT server config"
EOF
