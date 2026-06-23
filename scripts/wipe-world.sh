#!/usr/bin/env bash
# Delete the saved world and player/whitelist database for an environment,
# leaving server config, mods.yaml-derived config, the mod download cache,
# and the installed game server untouched. Use this to start a fresh map
# on the same volume without re-downloading the game server.
# Usage: scripts/wipe-world.sh <testing|prod> [--yes]
set -euo pipefail
export MSYS_NO_PATHCONV=1

ENVIRONMENT="${1:?Usage: wipe-world.sh <testing|prod> [--yes]}"
ASSUME_YES="${2:-}"

case "$ENVIRONMENT" in
  testing|prod) ;;
  *) echo "Environment must be 'testing' or 'prod', got '$ENVIRONMENT'" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../$ENVIRONMENT"

SERVER_NAME="$(grep -E '^PZ_SERVER_NAME=' .env | cut -d= -f2-)"
VOLUME="pz_${ENVIRONMENT}_data"

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  echo "Volume $VOLUME doesn't exist -- nothing to wipe." >&2
  exit 1
fi

if [ "$ASSUME_YES" != "--yes" ]; then
  echo "This will PERMANENTLY delete the saved world and player database"
  echo "for '$ENVIRONMENT' (server name: $SERVER_NAME, volume: $VOLUME)."
  echo "Server config, mods, and the installed game server are kept."
  read -r -p "Type 'wipe' to confirm: " confirm
  if [ "$confirm" != "wipe" ]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "Stopping $ENVIRONMENT server..."
docker compose stop pz

echo "Deleting world data and player database..."
docker run --rm -v "$VOLUME:/dest" alpine sh -c "
  set -e
  rm -rf /dest/Zomboid/Saves
  rm -f /dest/Zomboid/db/${SERVER_NAME}*
  mkdir -p /dest/Zomboid/Saves
  chown -R 1000:1000 /dest/Zomboid/Saves /dest/Zomboid/db
"

echo "Done. Start the server to generate a fresh world:"
echo "  (cd $ENVIRONMENT && docker compose up -d)"
