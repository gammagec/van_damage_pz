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
3. Pull the generated files out of the volume into this directory:
   ```bash
   docker compose cp pz:/home/ubuntu/Zomboid/Server/TestingServer.ini ./TestingServer.ini
   docker compose cp pz:/home/ubuntu/Zomboid/Server/TestingServer_SandboxVars.lua ./TestingServer_SandboxVars.lua
   ```
4. `git add TestingServer.ini TestingServer_SandboxVars.lua` and commit.

## Day-to-day changes

- **Mods**: edit the `Mods=` (mod IDs) and `WorkshopItems=` (Steam Workshop
  IDs) lines in `TestingServer.ini`.
- **Sandbox/world settings**: edit `TestingServer_SandboxVars.lua`.
- Commit, then redeploy (`scripts/deploy.sh testing ...` or `docker compose
  up -d --force-recreate` locally). Mods and most sandbox settings require
  a server restart to take effect anyway, so this matches normal workflow.
