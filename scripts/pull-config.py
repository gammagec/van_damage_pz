#!/usr/bin/env python3
"""Pull generated server config out of a running container into config/.

Reads PZ_SERVER_NAME from the environment's .env file, then copies
Zomboid/Server/<SERVER_NAME>* from the pz container into <env>/config/.

Usage: scripts/pull-config.py <testing|prod>
"""
import argparse
import io
import subprocess
import sys
import tarfile
from pathlib import Path


def read_env_var(env_file: Path, key: str) -> str:
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1:]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    env = args.environment
    repo_root = Path(__file__).resolve().parent.parent
    env_dir = repo_root / env
    env_file = env_dir / ".env"

    if not env_file.exists():
        print(f"{env}/.env not found", file=sys.stderr)
        sys.exit(1)

    server_name = read_env_var(env_file, "PZ_SERVER_NAME")
    if not server_name:
        print(f"PZ_SERVER_NAME not set in {env}/.env", file=sys.stderr)
        sys.exit(1)

    cid = subprocess.run(
        ["docker", "compose", "ps", "-q", "pz"],
        cwd=env_dir, capture_output=True, text=True,
    ).stdout.strip()

    running = cid and subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", cid],
        capture_output=True, text=True,
    ).stdout.strip() == "true"

    if not running:
        print(f"The '{env}' pz service isn't running. Start it first with:", file=sys.stderr)
        print(f"  (cd {env} && docker compose up -d)", file=sys.stderr)
        sys.exit(1)

    config_dir = env_dir / "config"
    config_dir.mkdir(exist_ok=True)

    print(f"Pulling Zomboid/Server/{server_name}* out of the '{env}' container into ./{env}/config ...")

    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "pz", "sh", "-c",
         f"cd /home/ubuntu/Zomboid/Server && tar cf - {server_name}*"],
        cwd=env_dir, capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.decode(errors="replace") or "(no error output)", file=sys.stderr)
        sys.exit(result.returncode)

    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tf:
        try:
            tf.extractall(config_dir, filter="data")
        except TypeError:
            tf.extractall(config_dir)  # Python < 3.12

    pulled = sorted(p.name for p in config_dir.iterdir() if server_name in p.name)
    print("Pulled:")
    for name in pulled:
        print(f"  {name}")

    print(f"""
Next steps:
  git -C "{env_dir}" status
  git add {env}/config
  git commit -m "Update {env} server config"
""")


if __name__ == "__main__":
    main()
