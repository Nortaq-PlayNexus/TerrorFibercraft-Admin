import os
import socket
import struct
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "admin"))

import ark_rcon  # noqa: E402
import pytest  # noqa: E402


def _packet(pkt_id, ptype, body=b""):
    payload = struct.pack("<ii", pkt_id, ptype) + body + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


class FakeServer:
    """Minimal source-engine RCON responder on a socketpair."""

    def __init__(self, auth_ok=True, command_response=b"players: 2"):
        self.auth_ok = auth_ok
        self.command_response = command_response
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.received = []

    def _recv_exact(self, conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def _read_packet(self, conn):
        hdr = self._recv_exact(conn, 4)
        if len(hdr) < 4:
            return None
        size = struct.unpack("<i", hdr)[0]
        data = self._recv_exact(conn, size)
        pid, ptype = struct.unpack("<ii", data[:8])
        body = data[8:-2]
        return pid, ptype, body

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        with conn:
            try:
                auth = self._read_packet(conn)
            except OSError:
                return
            self.received.append(auth)
            if not self.auth_ok:
                conn.sendall(_packet(-1, 2, b""))
                return
            conn.sendall(_packet(1, 2, b""))
            conn.sendall(_packet(0, 0, b""))  # terminator
            while True:
                try:
                    cmd = self._read_packet(conn)
                except OSError:
                    break
                if cmd is None:
                    break
                self.received.append(cmd)
                conn.sendall(_packet(cmd[0], 2, self.command_response))
                conn.sendall(_packet(0, 0, b""))  # terminator

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        try:
            self.sock.close()
        except Exception:
            pass


def test_encode_roundtrip():
    enc = ark_rcon._encode(5, 2, "cheat spawnactor x 1 2 3")
    assert struct.unpack("<i", enc[:4])[0] == len(enc[4:])
    pid, ptype = struct.unpack("<ii", enc[4:12])
    assert (pid, ptype) == (5, 2)


def test_encode_utf8_survives():
    enc = ark_rcon._encode(7, 2, "héllo ünïcode")
    assert "héllo".encode("utf-8") in enc


def test_auth_success_then_send():
    srv = FakeServer(auth_ok=True, command_response=b"players: 2").start()
    try:
        with ark_rcon.RconClient("127.0.0.1", srv.port, "pw") as r:
            out = r.send("listplayers")
        assert out == "players: 2"
    finally:
        srv.stop()
    assert srv.received and srv.received[0][2] == b"pw"


def test_send_many_skips_blanks():
    srv = FakeServer(command_response=b"ok").start()
    try:
        with ark_rcon.RconClient("127.0.0.1", srv.port, "pw") as r:
            results = r.send_many(["cheat a", "  ", "cheat b"])
        assert len(results) == 2
    finally:
        srv.stop()
    # The blank line is skipped, so only 2 EXECCOMMAND (type 2) packets land.
    # (The first received packet is the SERVERDATA_AUTH, ptype 3, not counted here.)
    cmd_pkts = [p for p in srv.received if p and p[1] == 2]
    assert len(cmd_pkts) == 2
    assert cmd_pkts[0][2].startswith(b"cheat a")
    assert cmd_pkts[1][2].startswith(b"cheat b")


def test_send_many_rate_limited():
    srv = FakeServer(command_response=b"x").start()
    try:
        with ark_rcon.RconClient("127.0.0.1", srv.port, "pw") as r:
            r.send_many(["cheat a", "cheat b"], interval=0.05)
    finally:
        srv.stop()


def test_broadcast_prefix():
    srv = FakeServer(command_response=b"")
    srv.start()
    try:
        with ark_rcon.RconClient("127.0.0.1", srv.port, "pw") as r:
            r.broadcast("maintenance soon")
        cmds = [p for p in srv.received if p and p[1] == 2]
        assert b'cheat broadcast "maintenance soon"' in cmds[-1][2]
    finally:
        srv.stop()


def test_list_players_parses_lines():
    srv = FakeServer(command_response=b"1. Alice\n2. Bob\n").start()
    try:
        with ark_rcon.RconClient("127.0.0.1", srv.port, "pw") as r:
            players = r.list_players()
        assert players == ["1. Alice", "2. Bob"]
    finally:
        srv.stop()


def test_bad_password_raises():
    srv = FakeServer(auth_ok=False).start()
    try:
        with pytest.raises(ark_rcon.RconError, match="auth failed"):
            ark_rcon.RconClient("127.0.0.1", srv.port, "wrong").connect()
    finally:
        srv.stop()


def test_reconnect_retries_then_raises():
    client = ark_rcon.RconClient("127.0.0.1", 1, "pw", max_retries=2,
                                 retry_base_delay=0.01, retry_max_delay=0.02)
    client.connect = lambda: (_ for _ in ()).throw(OSError("down"))
    with pytest.raises(ark_rcon.RconError, match="reconnect failed"):
        client._reconnect()


def test_send_transparently_reconnects(monkeypatch):
    srv = FakeServer(command_response=b"ok").start()
    calls = {"connect": 0}

    def flaky_connect():
        # Set directly on the instance via monkeypatch, so it is called with no args.
        calls["connect"] += 1
        if calls["connect"] == 1:
            raise OSError("first connect fails")
        # real connect (bound) for the retry
        return ark_rcon.RconClient.connect(client)

    client = ark_rcon.RconClient("127.0.0.1", srv.port, "pw", max_retries=2,
                                 retry_base_delay=0.01, retry_max_delay=0.02)
    monkeypatch.setattr(client, "connect", flaky_connect)
    try:
        out = client.send("listplayers")
        assert out == "ok"
        assert calls["connect"] >= 2
    finally:
        client.close()
        srv.stop()