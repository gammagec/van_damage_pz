Server config and mod selection for the **prod** environment.

This directory is read-only at runtime: the `config-sync` service copies
everything here into the `pz_prod_data` volume's `Zomboid/Server/` folder
before the server starts (see `../docker-compose.yml`). It's stamped back
in on every deploy, so any settings changed live via the in-game admin menu
get overwritten back to whatever is committed here — git is the only
source of truth.

## First-time bootstrap (this directory starts empty)

1. `docker compose up -d` — server starts with this empty, generates
   default config inside the volume.
2. Wait for the server to fully boot at least once (check `docker compose
   logs -f pz` until it reports ready).
3. From the repo root: `scripts/pull-config.sh prod` — pulls every
   generated `ProdServer*` file (ini, sandbox vars, spawn points/regions)
   out of the container into this directory.
4. `git add prod/config` and commit.

## Day-to-day changes

- **Mods**: don't hand-edit `Mods=`/`WorkshopItems=` in `ProdServer.ini`
  directly — edit `../mods.yaml` and run `scripts/sync-mods.py prod` (from
  the repo root) to regenerate those two lines.
- **Sandbox/world settings**: edit `ProdServer_SandboxVars.lua`.
- Commit, then redeploy (`scripts/deploy.sh prod ...` or `docker compose up
  -d --force-recreate` locally). Mods and most sandbox settings require a
  server restart to take effect anyway, so this matches normal workflow.
- If the server itself generates new files here, rerun
  `scripts/pull-config.sh prod` to recapture them before committing.

Consider copying a known-good config from `testing/config/` here (renaming
the files to match `PZ_SERVER_NAME=ProdServer`) once it's been validated,
instead of bootstrapping prod from scratch.
