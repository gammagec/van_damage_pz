#!/bin/bash
# Replaces the jthomastek/project-zomboid-server image's default
# /usr/local/sbin/bootstrap so PZ_BETA_BRANCH can select a SteamCMD beta
# branch (e.g. "unstable" for the build 42 test branch). Mirrors the
# original script exactly when PZ_BETA_BRANCH is unset/empty.
set -e

BETA_ARGS=()
if [ -n "${PZ_BETA_BRANCH:-}" ]; then
  BETA_ARGS=(-beta "$PZ_BETA_BRANCH")
fi

# SteamCMD's anonymous login intermittently fails the first attempt in a
# session with "ERROR! Failed to install app ... (Missing configuration)";
# retrying with no other change succeeds, so retry before giving up.
attempt=1
max_attempts=5
until steamcmd +force_install_dir /home/ubuntu/pzserver +login anonymous +app_update 380870 "${BETA_ARGS[@]}" +quit; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "steamcmd app_update failed after $max_attempts attempts" >&2
    exit 1
  fi
  echo "steamcmd app_update failed (attempt $attempt/$max_attempts), retrying..." >&2
  attempt=$((attempt + 1))
  sleep 5
done

cd /home/ubuntu/pzserver

./start-server.sh -Xms$PZ_JAVA_XMS -Xmx$PZ_JAVA_XMX -- \
    -adminusername $PZ_ADMIN_USERNAME \
    -adminpassword $PZ_ADMIN_PASSWORD \
    -servername $PZ_SERVER_NAME \
    -steamvac $PZ_STEAM_VAC
