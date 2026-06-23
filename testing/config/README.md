Server config and mod selection for the **testing** environment.

This directory is read-only at runtime: the `config-sync` service copies
everything here into the `pz_testing_data` volume's `Zomboid/Server/`
folder before the server starts (see `../docker-compose.yml`). It's stamped
back in on every deploy, so any settings changed live via the in-game admin
menu get overwritten back to whatever is committed here — git is the only
source of truth.

## First-time bootstrap (this directory starts empty)

1. `docker compose up -d` — server starts with this empty, generates
   default config inside the volume.
2. Wait for the server to fully boot at least once (check `docker compose
   logs -f pz` until it reports ready).
3. From the repo root: `scripts/pull-config.sh testing` — pulls every
   generated `TestingServer*` file (ini, sandbox vars, spawn points/regions)
   out of the container into this directory.
4. `git add testing/config` and commit.

## Day-to-day changes

- **Mods**: edit the `Mods=` (mod IDs) and `WorkshopItems=` (Steam Workshop
  IDs) lines in `TestingServer.ini`.
- **Sandbox/world settings**: edit `TestingServer_SandboxVars.lua`.
- Commit, then redeploy (`scripts/deploy.sh testing ...` or `docker compose
  up -d --force-recreate` locally). Mods and most sandbox settings require
  a server restart to take effect anyway, so this matches normal workflow.
- If the server itself generates new files here (e.g. spawn regions edited
  in-game, or a new file added by a PZ update), rerun
  `scripts/pull-config.sh testing` to recapture them before committing.
