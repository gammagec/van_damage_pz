# Project Zomboid Server

Docker Compose setup for a Project Zomboid dedicated server, with separate
`testing/` and `prod/` configurations. Both use the
[jthomastek/project-zomboid-server](https://github.com/JThomasTek/project-zomboid-server-docker)
image. `testing` tracks `:latest`; `prod` is pinned to `:1.0.0` for stability.

## Layout

- `testing/` — testing config (`docker-compose.yml`, `.env`, `config/`)
- `prod/` — prod config (`docker-compose.yml`, `.env`, `config/`)
- `scripts/deploy.sh` — deploys to a remote host over SSH
- `scripts/pull-config.sh` — pulls generated server config out of a running container into `config/`
- `scripts/sync-mods.py` — writes `Mods=`/`WorkshopItems=` into `config/<name>.ini` from `mods.yaml`
- `scripts/pz-bootstrap.sh` — replaces the image's default startup script to support `PZ_BETA_BRANCH`
- `scripts/add-mod.py` — looks up a Workshop ID's title on Steam and appends an entry to `mods.yaml`
- `scripts/sync-submods.py` — resolves `mod_id`/`sub_mods` in `mods.yaml` from already-downloaded Workshop content
- `scripts/wipe-world.sh` — deletes the saved world/player database for a fresh map, keeping config and the installed game server
- `scripts/fix-mod-case.sh` — creates lowercase symlinks for mod folders so Windows-authored mods work on Linux's case-sensitive filesystem

Each environment has its own named Docker volume (`pz_testing_data` /
`pz_prod_data`), so testing and prod never share save data, even if run on
the same machine.

## First-time setup (any host: local, testing machine, or prod machine)

Secrets (the admin password) are **not** committed to git. On every host
that will run a given environment, copy the example once and fill it in:

```bash
cp testing/.env.secrets.example testing/.env.secrets
# edit testing/.env.secrets and set a real PZ_ADMIN_PASSWORD
```

(same for `prod/.env.secrets`). `.env.secrets` is gitignored — it stays on
the host, it's never pushed or pulled.

## Local smoke test

From the repo root:

```bash
cd testing   # or prod
docker compose up -d
docker compose logs -f
```

Stop with `docker compose down` (data persists in the named volume; add
`-v` to wipe it). To pick up new config after editing `config/` or `.env`,
use `docker compose up -d --force-recreate` (see "Server config & mods"
below for why `--force-recreate` matters).

## Editing config

**Non-secret settings** (server name, memory, ports) live in `testing/.env`
/ `prod/.env` and are checked into git. Edit, commit, push like normal code:

```bash
git add testing/.env
git commit -m "Bump testing server memory to 6g"
git push
```

**Server settings and mods** (sandbox options, `Mods=`/`WorkshopItems=`)
live in `testing/config/` / `prod/config/` — see the `README.md` in each
for the one-time bootstrap and day-to-day editing workflow. The short
version: those files are the single source of truth. A `config-sync`
helper service stamps them into the running server's volume on every
`docker compose up -d --force-recreate`, which overwrites any settings
changed live through the in-game admin menu — so config drift never
survives a deploy. Always use `--force-recreate` (the deploy script
already does) rather than a plain `up -d`, otherwise `config-sync` won't
rerun and stale volume state will stick around.

**Mods** are managed in `testing/mods.yaml` / `prod/mods.yaml` rather than
hand-editing the ini's `Mods=`/`WorkshopItems=` lines directly. Each entry
is one Steam Workshop item; items that bundle several sub-mods can disable
individual sub-mods while keeping the rest (see the comments at the top of
`testing/mods.yaml` for the full schema).

Adding a mod is a two-step process, split so the slow part (the actual
Workshop download) only happens once, done by the server itself instead of
by tooling:

1. `scripts/add-mod.py testing <workshop_id>` (or omit the ID and it'll
   ask) — fast, just looks up the title from the Steam Web API and appends
   a `workshop_id`-only entry. It does **not** know the mod_id yet; the
   public API doesn't expose it, only the item's own `mod.info` does.
2. `scripts/sync-mods.py testing` and deploy as normal. The new entry adds
   its `workshop_id` to `WorkshopItems=` (contributing nothing to `Mods=`
   yet), so the server downloads it on its own the next time it starts.
3. Once it's downloaded, run `scripts/sync-submods.py testing` — this
   reads `mod.info` straight out of the already-downloaded content in the
   environment's volume (no separate SteamCMD call, so it's fast) and
   fills in `mod_id` (single mod) or `sub_mods` (multiple bundled mods,
   asking nothing — newly found sub-mods default enabled; edit
   `mods.yaml` by hand to disable any). Entries that are already resolved
   are left alone; pass `--force` to re-resolve them too (existing
   `enabled: false` choices are preserved for sub-mod ids that still
   exist).
4. `scripts/sync-mods.py testing` again to write the now-resolved
   `Mods=`, then redeploy (restart) so the mod actually activates.

```bash
git add testing/mods.yaml testing/config
git commit -m "Enable ExampleMod"
```

Requires `python3` with `pyyaml`. `add-mod.py` and `sync-mods.py` need no
Docker access (the former just makes an HTTPS call, the latter only edits
the checked-in ini); `sync-submods.py` needs `docker` to read the
environment's volume, but talks only to the local Docker daemon, not Steam.

**Unstable/beta build**: set `PZ_BETA_BRANCH` in `testing/.env` or
`prod/.env` to a SteamCMD beta branch name (e.g. `unstable` for the build 42
test branch) to run that build instead of the default stable branch. Leave
it empty for stable. The `pz` service overrides the image's default startup
command with `scripts/pz-bootstrap.sh`, which passes `-beta
$PZ_BETA_BRANCH` through to `steamcmd` when set (and behaves identically to
the stock image when it's empty). Restart with `docker compose up -d
--force-recreate` to switch branches.

Switching branches on a volume with existing saves can make them fail to
load (world formats can differ between branches, e.g. build 41 vs. build
42) — use this on testing with a save you're fine losing, or wipe the world
first with `scripts/wipe-world.sh testing` (see below).

Note: SteamCMD's anonymous login intermittently fails the first attempt in
a session with `ERROR! Failed to install app ... (Missing configuration)`
regardless of branch — `pz-bootstrap.sh` retries automatically (5 attempts,
5s apart) before giving up.

## Fixing mod case sensitivity

Some mods are authored on Windows and reference their own folder in lowercase
within their Lua scripts (e.g. `require("lifestyle/...")`), but ship with a
mixed-case folder name (e.g. `mods/Lifestyle/`). Linux's case-sensitive
filesystem rejects those references, producing `FileNotFoundException` errors
at startup.

Run this once after the server has downloaded its mods (and again whenever you
add new mods):

```bash
scripts/fix-mod-case.sh testing
```

It creates a lowercase symlink next to each mod folder whose name differs from
its own lowercase form (e.g. `lifestyle -> Lifestyle`). Symlinks that already
exist are silently skipped, so it's safe to rerun. It only touches
`mods/` subdirectories inside Workshop content — it never touches saves or
config.

## Wiping the world

`scripts/wipe-world.sh <testing|prod>` deletes the saved map and player
database for a fresh start, stopping the server first and asking you to
type `wipe` to confirm (pass `--yes` to skip the prompt, e.g. for
non-interactive use). It leaves server config, `mods.yaml`-derived config,
and the installed game server alone — it does **not** re-download
anything. This is deliberately more surgical than `docker compose down -v`:
that would also delete the installed game server (it shares the same
volume as the saves), forcing a full multi-GB reinstall just to reset a
map.

```bash
scripts/wipe-world.sh testing
# then bring it back up with a fresh world:
(cd testing && docker compose up -d)
```

## Deploying to a remote host

The remote host keeps its own git clone of this repo and pulls on deploy
(make sure it's been cloned once, with `.env.secrets` created per the
first-time setup above). Then from your machine:

```bash
scripts/deploy.sh testing pz-test-host
scripts/deploy.sh prod pz-prod-host
```

This SSHes in, runs `git pull --ff-only`, then `docker compose pull && docker
compose up -d` in the target environment's directory. Default remote repo
path is `~/van_damage_pz`; override with a third argument if it's cloned
elsewhere:

```bash
scripts/deploy.sh prod pz-prod-host /opt/van_damage_pz
```

## Ports

| | game | players | host port vars |
|---|---|---|---|
| testing | 8766/udp | 16261-16262/udp | `HOST_GAME_PORT`, `HOST_PLAYER_PORT_RANGE` |
| prod | 8866/udp | 16361-16362/udp | `HOST_GAME_PORT`, `HOST_PLAYER_PORT_RANGE` |

Testing and prod use different default host ports so both can run
side-by-side on the same machine (e.g. during a local smoke test) without
colliding.
