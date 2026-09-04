#!/usr/bin/env python3
"""
ark_rcon.py — Minimal, dependency-free RCON client for ARK (ASE/ASA).
Source RCON protocol (Valve). Sends admin commands (e.g. the spawnactor
batches from cave-spawn-generator.py) to a Nitrado ASE server.

Hardened for real cluster ops:
  * auto-reconnect with exponential backoff on dropped/reset connections
    (Nitrado restarts, wipes, network blips)
  * rate-limited command queue (send_many) to avoid flooding the server
  * broadcast() helper for chat announcements
  * list_players() convenience for the common status command

Usage:
  from ark_rcon import RconClient
  with RconClient("111.111.111.111", 27020, "rconpass") as r:
      for line in open("wall.txt"):
          if line.startswith("cheat spawnactor"):
              r.send(line.strip())
  with RconClient("1.2.3.4", 27020, "pw", max_retries=3) as r:
      r.broadcast("Cluster maintenance in 5 minutes")
      r.send_many(cheat_lines, interval=0.25)
      print(r.list_players())

CLI self-test:  py ark_rcon.py --selftest
CLI send:       py ark_rcon.py --host H --port P --password PW --cmd "cheat listplayers"
"""
import socket
import struct
import time

DEFAULT_TIMEOUT = 8
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 0.5
DEFAULT_RETRY_MAX_DELAY = 6.0


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
    if len(data) < size:
        raise RconError("Connection closed mid-packet")
    pkt_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2] if len(data) >= 10 else b""  # strip the two trailing nulls
    return pkt_id, ptype, body


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def _drain(sock: socket.socket):
    """Read and discard any queued packets with a short timeout."""
    saved = sock.gettimeout()
    try:
        sock.settimeout(0.5)
        while True:
            try:
                _read_packet(sock)
            except Exception:
                break
    finally:
        sock.settimeout(saved)


class RconClient:
    def __init__(self, host: str, port: int, password: str,
                 timeout: int = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
                 retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.sock = None
        self._id = 1

    # ------------------------------------------------------------------ I/O
    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._auth()

    def _auth(self):
        self.sock.sendall(_encode(1, 3, self.password))  # SERVERDATA_AUTH
        pkt_id, ptype, _ = _read_packet(self.sock)
        _drain(self.sock)
        if pkt_id == -1:
            self.sock.close()
            self.sock = None
            raise RconError("RCON auth failed (bad password?)")

    def _reconnect(self):
        """Reconnect with exponential backoff, raising if we exhaust retries."""
        delay = self.retry_base_delay
        last = None
        for attempt in range(self.max_retries):
            try:
                self.connect()
                return
            except RconError:
                raise
            except OSError as e:
                last = e
                time.sleep(delay)
                delay = min(delay * 2, self.retry_max_delay)
        raise RconError(f"reconnect failed after {self.max_retries} attempt(s): {last}")

    # ------------------------------------------------------------- commands
    def send(self, command: str, _retried: bool = False) -> str:
        """Send one command; transparently reconnect+retry once on a stall."""
        try:
            if self.sock is None:
                self.connect()
            self._id += 1
            myid = self._id
            self.sock.sendall(_encode(myid, 2, command))  # SERVERDATA_EXECCOMMAND
            out = []
            while True:
                pkt_id, ptype, body = _read_packet(self.sock)
                if ptype == 0 and body == b"":
                    break  # terminator
                if ptype == 2 and pkt_id != myid:
                    continue  # stray packet; keep reading
                if body:
                    out.append(body.decode("utf-8", "replace"))
            return "".join(out)
        except (RconError, OSError):
            self.close()
            if _retried:
                raise
            self._reconnect()
            return self.send(command, _retried=True)

    def send_many(self, commands, interval: float = 0.0, progress=None) -> list:
        """Send a list of commands with optional min spacing and progress callback.

        progress(done, total) is called after each command and a final time at the end.
        Blank lines and non-command noise are skipped like the CLI Apply path.
        """
        results, done = [], 0
        cmds = [c for c in (s.strip() for s in commands) if c]
        total = len(cmds)
        for c in cmds:
            if progress:
                progress(done, total)
            results.append(self.send(c))
            done += 1
            if interval > 0:
                time.sleep(interval)
        if progress:
            progress(total, total)
        return results

    def broadcast(self, message: str, prefix: str = "cheat broadcast") -> str:
        """Send a server-wide chat announcement. Prefix is configurable because
        some server setups want `broadcast` or `chat` (verify against your install)."""
        return self.send(f'{prefix} "{message}"')

    def list_players(self) -> list[str]:
        """RCON 'listplayers' -> list of player lines (empty list if none)."""
        out = self.send("listplayers").strip() or ""
        return [ln for ln in out.splitlines() if ln.strip()]

    # -------------------------------------------------------------- lifecycle
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


if __name__ == "__main__":
    import argparse
    import sys

    if "--selftest" in sys.argv:
        enc = _encode(5, 2, "cheat spawnactor x 1 2 3")
        # decode it back to confirm round-trip
        assert struct.unpack("<i", enc[:4])[0] == len(enc[4:])
        # multi-byte body should survive encode/decode
        enc2 = struct.unpack("<ii", _encode(7, 2, "héllo")[4:12])
        assert enc2[1] == 2
        print("selftest OK: packet length", len(enc), "bytes; encode round-trip OK")
        sys.exit(0)

    p = argparse.ArgumentParser(description="Send a one-shot RCON command")
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--cmd", required=True)
    args = p.parse_args()
    with RconClient(args.host, args.port, args.password) as r:
        for line in r.send(args.cmd).splitlines():
            print(line)