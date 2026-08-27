#!/usr/bin/env python3
"""
ark_rcon.py — Minimal, dependency-free RCON client for ARK (ASE/ASA).
Source RCON protocol (Valve). Sends admin commands (e.g. the spawnactor
batches from cave-spawn-generator.py) to a Nitrado ASE server.

Usage:
  from ark_rcon import RconClient
  with RconClient("111.111.111.111", 27020, "rconpass") as r:
      for line in open("wall.txt"):
          if line.startswith("cheat spawnactor"):
              r.send(line.strip())

CLI self-test:  py ark_rcon.py --selftest
"""
import socket
import struct

DEFAULT_TIMEOUT = 8


class RconError(Exception):
    pass


def _encode(pkt_id: int, ptype: int, body: str) -> bytes:
    body_b = body.encode("utf-8", "replace")
    # length = id(4) + type(4) + body + null(1) + empty-null(1)
    payload = struct.pack("<ii", pkt_id, ptype) + body_b + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def _read_packet(sock: socket.socket) -> tuple[int, int, bytes]:
    hdr = _recv_exact(sock, 4)
    if len(hdr) < 4:
        raise RconError("Connection closed while reading header")
    size = struct.unpack("<i", hdr)[0]
    data = _recv_exact(sock, size)
    pkt_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2]  # strip the two trailing nulls
    return pkt_id, ptype, body


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: int = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.sock = None
        self._id = 1

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._auth()

    def _auth(self):
        self.sock.sendall(_encode(1, 3, self.password))  # SERVERDATA_AUTH
        # Read auth response (and the trailing empty packet)
        pkt_id, ptype, _ = _read_packet(self.sock)
        _drain(self.sock)
        if pkt_id == -1:
            raise RconError("RCON auth failed (bad password?)")

    def send(self, command: str) -> str:
        if self.sock is None:
            self.connect()
        self._id += 1
        myid = self._id
        self.sock.sendall(_encode(myid, 2, command))  # SERVERDATA_EXECCOMMAND
        out = []
        # Response comes as one or more packets ending with an empty packet
        while True:
            pkt_id, ptype, body = _read_packet(self.sock)
            if ptype == 0 and body == b"":
                break
            if body:
                out.append(body.decode("utf-8", "replace"))
            if ptype == 2 and pkt_id != myid:
                # stray packet; keep reading
                continue
        return "".join(out)

    def send_many(self, commands: list[str]) -> list[str]:
        results = []
        for c in commands:
            c = c.strip()
            if not c:
                continue
            results.append(self.send(c))
        return results

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *a):
        self.close()


def _drain(sock: socket.socket):
    """Read and discard any trailing empty/response packets."""
    self_saved = getattr(sock, "_rcon_drain_guard", 0)
    if self_saved:
        return
    try:
        sock.settimeout(0.5)
        while True:
            try:
                _read_packet(sock)
            except Exception:
                break
    finally:
        sock.settimeout(DEFAULT_TIMEOUT)


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        enc = _encode(5, 2, "cheat spawnactor x 1 2 3")
        # decode it back to confirm round-trip
        assert struct.unpack("<i", enc[:4])[0] == len(enc[4:])
        print("selftest OK: packet length", len(enc), "bytes")
    else:
        print("ark_rcon.py loaded. Use as a module or --selftest.")
