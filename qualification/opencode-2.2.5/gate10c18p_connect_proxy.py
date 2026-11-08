#!/usr/bin/env python3
"""Gate 10C.18p — single-destination disposable CONNECT relay.

This is a no-credential *network topology test only*. It is not production-ready:
the relay is trusted code, and Docker's internal bridge must confine its client.
"""
import select
import socket
import socketserver
import sys
import time

HOST = "api.github.com"
PORT = 443
LISTEN_PORT = 3128
MAX_HEADERS = 4096
MAX_BYTES = 512 * 1024
DEADLINE_SEC = 12

def allowed(raw):
    """Only one authority and two narrowly defined benign HTTP headers."""
    if not isinstance(raw, bytes) or len(raw) > MAX_HEADERS:
        return False
    if not raw.endswith(b"\r\n\r\n"):
        return False
    try:
        lines = raw[:-4].decode("ascii").split("\r\n")
    except UnicodeDecodeError:
        return False
    if not lines or lines[0] != "CONNECT api.github.com:443 HTTP/1.1":
        return False
    seen_host = False
    for line in lines[1:]:
        if line == "Host: api.github.com:443" and not seen_host:
            seen_host = True
        elif line == "Proxy-Connection: Keep-Alive":
            continue
        else:
            return False
    return seen_host

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(4)
        data = bytearray()
        try:
            while b"\r\n\r\n" not in data and len(data) <= MAX_HEADERS:
                part = self.request.recv(1024)
                if not part:
                    break
                data.extend(part)
            if not allowed(bytes(data)):
                self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                return
            try:
                upstream = socket.create_connection((HOST, PORT), timeout=5)
            except (socket.timeout, OSError):
                self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                return
            with upstream:
                upstream.setblocking(False)
                self.request.setblocking(False)
                self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                sockets = [self.request, upstream]
                budget = MAX_BYTES
                stop_at = time.monotonic() + DEADLINE_SEC
                while budget > 0 and time.monotonic() < stop_at:
                    readable, _, _ = select.select(sockets, [], [], 1.0)
                    for source in readable:
                        try:
                            payload = source.recv(min(8192, budget))
                        except (BlockingIOError, InterruptedError):
                            continue
                        if not payload:
                            return
                        target = upstream if source is self.request else self.request
                        target.sendall(payload)
                        budget -= len(payload)
        except (OSError, ValueError, socket.timeout):
            pass

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(2)
    with Server(("0.0.0.0", LISTEN_PORT), Handler) as server:
        server.serve_forever(poll_interval=0.2)
