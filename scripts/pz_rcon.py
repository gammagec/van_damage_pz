"""Minimal Source RCON client for Project Zomboid servers.

Imported by restart-with-warning.py and mod-update-watcher.py.
Not a standalone script.

Source RCON wire format (little-endian):
  [size: i32][id: i32][type: i32][body: utf-8 + \\x00][\\x00]
  size = 4 + 4 + len(body_bytes) + 1 + 1
"""
import socket
import struct

_AUTH = 3
_EXEC = 2
_AUTH_RESP = 2
_RESP_VAL = 0


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("RCON socket closed unexpectedly")
        buf += chunk
    return buf


def _pack(req_id: int, ptype: int, body: str) -> bytes:
    body_b = body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<iii", len(body_b) + 8, req_id, ptype) + body_b


def _unpack(sock: socket.socket) -> tuple[int, int, str]:
    size = struct.unpack("<i", _recv_exact(sock, 4))[0]
    data = _recv_exact(sock, size)
    req_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode("utf-8", errors="replace")
    return req_id, ptype, body


class RconError(Exception):
    pass


class Rcon:
    """Context-manager RCON connection.

    Usage:
        with Rcon("pz-testing", 27015, "secret") as rcon:
            rcon.run('servermsg "hello"')
            rcon.run("save")
    """

    def __init__(self, host: str, port: int, password: str, timeout: float = 10.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.sendall(_pack(1, _AUTH, password))
        # Drain packets until we get the auth response (type == _AUTH_RESP and id != 0).
        # Some servers send an empty RESP_VAL before the real auth response.
        while True:
            rid, ptype, _ = _unpack(self._sock)
            if ptype == _AUTH_RESP and rid != 0:
                break  # id == -1 means bad password (checked below)
        if rid == -1:
            self._sock.close()
            raise RconError("RCON authentication failed — check PZ_RCON_PASSWORD")

    def run(self, command: str) -> str:
        self._sock.sendall(_pack(2, _EXEC, command))
        _, _, body = _unpack(self._sock)
        return body

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> "Rcon":
        return self

    def __exit__(self, *_) -> None:
        self.close()


def try_rcon(host: str, port: int, password: str, command: str) -> bool:
    """Send one RCON command, returning False (and logging) on any error."""
    try:
        with Rcon(host, port, password) as r:
            r.run(command)
        return True
    except Exception as exc:
        print(f"[rcon] {command!r} failed: {exc}", flush=True)
        return False
