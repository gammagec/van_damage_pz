# Project Zomboid Server

Docker Compose setup for a Project Zomboid dedicated server, with separate
`testing/` and `prod/` configurations. Both use the
[jthomastek/project-zomboid-server](https://github.com/JThomasTek/project-zomboid-server-docker)
image. `testing` tracks `:latest`; `prod` is pinned to `:1.0.0` for stability.

## Layout

- `testing/` — testing config (`docker-compose.yml`, `.env`, `config/`)
- `prod/` — prod config (`docker-compose.yml`, `.env`, `config/`)
- `scripts/deploy.sh` — deploys to a remote host over SSH

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
