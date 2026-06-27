#!/usr/bin/env python3
"""Sync PZ_RCON_PASSWORD between the server ini and .env.secrets.

Reads RCONPassword from the environment's server ini (the git-tracked
config, not the live volume) and writes it to <env>/.env.secrets as
PZ_RCON_PASSWORD.  If the ini has no password set, a random one is
generated, written to both the ini and .env.secrets, and the server
must be restarted for the change to take effect (the bootstrap script
injects it into the live ini on startup).

Usage: scripts/pull-rcon-password.py <testing|prod>
"""
import argparse
import re
import secrets
import sys
from pathlib import Path


def _read_env_var(env_file: Path, key: str) -> str:
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1:]
    return ""


def _read_ini_var(ini_file: Path, key: str) -> str:
    for line in ini_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1:].strip()
    return ""


def _set_ini_var(ini_file: Path, key: str, value: str) -> None:
    text = ini_file.read_text()
    new_line = f"{key}={value}"
    if re.search(rf"^{re.escape(key)}=", text, re.MULTILINE):
        text = re.sub(rf"^{re.escape(key)}=.*", new_line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"
    ini_file.write_text(text)


def _set_secrets_var(secrets_file: Path, key: str, value: str) -> None:
    if secrets_file.exists():
        text = secrets_file.read_text()
        if re.search(rf"^{re.escape(key)}=", text, re.MULTILINE):
            text = re.sub(rf"^{re.escape(key)}=.*", f"{key}={value}", text, flags=re.MULTILINE)
            secrets_file.write_text(text)
            return
    # Append
    with secrets_file.open("a") as f:
        f.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    env = args.environment
    repo_root = Path(__file__).resolve().parent.parent
    env_dir = repo_root / env
    env_file = env_dir / ".env"
    secrets_file = env_dir / ".env.secrets"

    server_name = _read_env_var(env_file, "PZ_SERVER_NAME")
    if not server_name:
        print(f"PZ_SERVER_NAME not set in {env}/.env", file=sys.stderr)
        sys.exit(1)

    ini_file = env_dir / "config" / f"{server_name}.ini"
    if not ini_file.exists():
        print(f"Config not found: {ini_file}", file=sys.stderr)
        print("Run scripts/pull-config.py first to pull it from the container.", file=sys.stderr)
        sys.exit(1)

    ini_password = _read_ini_var(ini_file, "RCONPassword")
    secrets_password = _read_secrets_var(secrets_file, "PZ_RCON_PASSWORD") if secrets_file.exists() else ""

    if ini_password:
        # Password already set in ini — sync it to .env.secrets.
        print(f"Found RCONPassword in {ini_file.name}.")
        _set_secrets_var(secrets_file, "PZ_RCON_PASSWORD", ini_password)
        print(f"Written PZ_RCON_PASSWORD to {env}/.env.secrets.")
    else:
        # No password in ini — generate one, write to both ini and .env.secrets.
        print(f"RCONPassword is blank in {ini_file.name}.")
        if secrets_password:
            # .env.secrets already has a password — push it into the ini.
            print(f"PZ_RCON_PASSWORD already set in {env}/.env.secrets — writing it to ini.")
            _set_ini_var(ini_file, "RCONPassword", secrets_password)
            print(f"Updated {ini_file.name}.")
            print()
            print("Commit the updated ini, then restart the server for the change to take effect:")
            print(f"  git add {env}/config/{ini_file.name}")
            print(f'  git commit -m "set RCON password in {env} ini"')
        else:
            # Nothing anywhere — generate a fresh password.
            new_password = secrets.token_urlsafe(24)
            print(f"Generating a new RCON password ...")
            _set_ini_var(ini_file, "RCONPassword", new_password)
            _set_secrets_var(secrets_file, "PZ_RCON_PASSWORD", new_password)
            print(f"Written to {ini_file.name} and {env}/.env.secrets.")
            print()
            print("Commit the updated ini, then restart the server for the change to take effect:")
            print(f"  git add {env}/config/{ini_file.name}")
            print(f'  git commit -m "set RCON password in {env} ini"')


def _read_secrets_var(secrets_file: Path, key: str) -> str:
    for line in secrets_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1:].strip()
    return ""


if __name__ == "__main__":
    main()
