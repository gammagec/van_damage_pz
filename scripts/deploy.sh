#!/usr/bin/env bash
# Deploy testing or prod to a remote host: SSH in, git pull, then docker compose up -d.
# Usage: scripts/deploy.sh <testing|prod> <ssh-host> [remote-repo-path]
set -euo pipefail

ENVIRONMENT="${1:?Usage: deploy.sh <testing|prod> <ssh-host> [remote-repo-path]}"
SSH_HOST="${2:?Usage: deploy.sh <testing|prod> <ssh-host> [remote-repo-path]}"
REMOTE_PATH="${3:-~/van_damage_pz}"

case "$ENVIRONMENT" in
  testing|prod) ;;
  *) echo "Environment must be 'testing' or 'prod', got '$ENVIRONMENT'" >&2; exit 1 ;;
esac

ssh "$SSH_HOST" "
  set -euo pipefail
  cd '$REMOTE_PATH'
  git pull --ff-only
  cd '$ENVIRONMENT'
  docker compose pull
  docker compose up -d --force-recreate
"
# --force-recreate reruns config-sync so committed config/ overwrites the
# volume's copy on every deploy, undoing any drift from in-game admin edits.
