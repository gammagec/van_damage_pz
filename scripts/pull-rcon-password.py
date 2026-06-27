#!/usr/bin/env python3
"""Sync PZ_RCON_PASSWORD between the server ini and .env.secrets.

The server ini (TestingServer.ini / ProdServer.ini) is committed to git and
must NEVER contain the real RCON password.  Instead, pz-bootstrap.sh injects
PZ_RCON_PASSWORD from .env.secrets into the live ini at container startup.

This script handles three states:

  1. Password in .env.secrets, ini is blank (correct state)
       → confirms everything is already set up correctly, nothing to do.

  2. Password in ini, not in .env.secrets (migrating a manually configured server)
       → copies the password to .env.secrets, then CLEARS the ini so the secret
          is no longer in a git-tracked file.  Commit the cleared ini afterwards.

  3. Both blank
       → generates a random password and writes it ONLY to .env.secrets.
          The bootstrap will inject it into the live ini on next server startup.
          Nothing is written to the ini, so nothing secret ever touches git.

Usage: scripts/pull-rcon-password.py <testing|prod>
"""
import argparse
import re
import secrets
import sys
from pathlib import Path


def _read_env_var(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1:]
    return ""


def _set_ini_var(ini_file: Path, key: str, value: str) -> None:
    text = ini_file.read_text()
    text = re.sub(rf"^{re.escape(key)}=.*", f"{key}={value}", text, flags=re.MULTILINE)
    ini_file.write_text(text)


def _set_secrets_var(secrets_file: Path, key: str, value: str) -> None:
    if secrets_file.exists():
        text = secrets_file.read_text()
        if re.search(rf"^{re.escape(key)}=", text, re.MULTILINE):
            text = re.sub(rf"^{re.escape(key)}=.*", f"{key}={value}", text, flags=re.MULTILINE)
            secrets_file.write_text(text)
            return
    with secrets_file.open("a") as f:
        f.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    env = args.environment
    repo_root = Path(__file__).resolve().parent.parent
    env_dir = repo_root / env
    secrets_file = env_dir / ".env.secrets"

    server_name = _read_env_var(env_dir / ".env", "PZ_SERVER_NAME")
    if not server_name:
        print(f"PZ_SERVER_NAME not set in {env}/.env", file=sys.stderr)
        sys.exit(1)

    ini_file = env_dir / "config" / f"{server_name}.ini"
    if not ini_file.exists():
        print(f"Config not found: {ini_file}", file=sys.stderr)
        print("Run scripts/pull-config.py first to pull it from the container.", file=sys.stderr)
        sys.exit(1)

    ini_password     = _read_env_var(ini_file, "RCONPassword")
    secrets_password = _read_env_var(secrets_file, "PZ_RCON_PASSWORD")

    if secrets_password and not ini_password:
        # Correct state — nothing to do.
        print(f"OK: PZ_RCON_PASSWORD is set in {env}/.env.secrets and the ini is blank.")
        print("pz-bootstrap.sh will inject it into the live ini at next server startup.")

    elif ini_password:
        # Password is hardcoded in the ini — migrate it out before it ends up in git.
        print(f"Found RCONPassword in {ini_file.name} — migrating to .env.secrets ...")
        _set_secrets_var(secrets_file, "PZ_RCON_PASSWORD", ini_password)
        print(f"Written PZ_RCON_PASSWORD to {env}/.env.secrets.")

        _set_ini_var(ini_file, "RCONPassword", "")
        print(f"Cleared RCONPassword in {ini_file.name} (password must not live in git).")
        print()
        print("Commit the cleared ini:")
        print(f"  git add {env}/config/{ini_file.name}")
        print(f'  git commit -m "remove hardcoded RCON password from {env} ini"')

    else:
        # Both blank — generate a fresh password and write it only to .env.secrets.
        new_password = secrets.token_urlsafe(24)
        print("Both ini and .env.secrets have no RCON password — generating one ...")
        _set_secrets_var(secrets_file, "PZ_RCON_PASSWORD", new_password)
        print(f"Written PZ_RCON_PASSWORD to {env}/.env.secrets.")
        print("The ini is unchanged (the bootstrap injects the password at runtime).")
        print()
        print("Restart the server to activate RCON:")
        print(f"  (cd {env} && docker compose restart pz)")


if __name__ == "__main__":
    main()
