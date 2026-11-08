#!/usr/bin/env python3
"""Gate 10C.18r — one-connection synthetic-only disposable CONNECT relay.

This is an *invalid-synthetic-token* single-MCP-tool-call test only; not production-ready:
the relay is trusted code, and Docker's internal bridge must confine its client.
"""
import select
import socket
import socketserver
import threading
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
        elif line in ("Proxy-Connection: Keep-Alive", "User-Agent: Go-http-client/1.1"):
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
            # Exactly one CONNECT tunnel; no request text, headers or token logged.
            with self.server.admission_lock:
                if self.server.admitted:
                    self.request.sendall(b"HTTP/1.1 429 Too Many Requests\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    print("GATE10C18R_PROXY_ADDITIONAL_CONNECT=DENIED", flush=True)
                    return
                self.server.admitted = True
                print("GATE10C18R_PROXY_CONNECT_ADMITTED=1", flush=True)
            try:
                upstream = socket.create_connection((HOST, PORT), timeout=5)
            except (socket.timeout, OSError):
                self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                return
            with upstream:
                # select() determines readability; bounded blocking sendall()
                # avoids losing short TLS records to EWOULDBLOCK.
                upstream.settimeout(3)
                self.request.settimeout(3)
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

    def __init__(self, *args, **kwargs):
        self.admitted = False
        self.admission_lock = threading.Lock()
        super().__init__(*args, **kwargs)

if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(2)
    with Server(("0.0.0.0", LISTEN_PORT), Handler) as server:
        server.serve_forever(poll_interval=0.2)
