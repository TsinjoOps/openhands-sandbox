#!/usr/bin/env python3
"""Gate 10C.18p — no-secret client tests of a disposable CONNECT topology."""
import os
import socket
import ssl
import sys
import time

PROXY = "tsinjoops-github-egress"
PORT = 3128
REQUEST = b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\n\r\n"

def require(ok, code):
    if not ok:
        raise RuntimeError(code)

def recv_head(sock):
    data = bytearray()
    while b"\r\n\r\n" not in data:
        part = sock.recv(1024)
        require(bool(part), "PROXY_EARLY_CLOSE")
        data.extend(part)
        require(len(data) <= 4096, "PROXY_HEADER_LIMIT")
    return bytes(data).split(b"\r\n", 1)[0]

def connect_proxy(payload):
    conn = socket.create_connection((PROXY, PORT), timeout=5)
    conn.settimeout(5)
    conn.sendall(payload)
    return conn

def rejected(payload):
    with connect_proxy(payload) as conn:
        return recv_head(conn) == b"HTTP/1.1 403 Forbidden"

def direct_denied(family, address, port):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect((address, port))
            return False
    except (socket.timeout, OSError):
        return True

def main():
    require(os.geteuid() == 10001, "EXPECTED_UID_10001")
    for key in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN",
                "GH_TOKEN", "OPENROUTER_API_KEY", "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY"):
        require(not os.environ.get(key), "CREDENTIAL_ENV_FOUND")
    print("NO_REAL_CREDENTIALS_OR_MODEL=YES", flush=True)

    deadline = time.monotonic() + 15
    while True:
        try:
            with socket.create_connection((PROXY, PORT), timeout=2):
                break
        except OSError:
            require(time.monotonic() < deadline, "PROXY_NOT_READY")
            time.sleep(0.4)
    print("INTERNAL_PROXY_REACHABLE=PASS", flush=True)

    invalid = (
        b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n",
        b"CONNECT api.github.com:80 HTTP/1.1\r\nHost: api.github.com:80\r\n\r\n",
        b"CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443\r\n\r\n",
        b"GET http://api.github.com HTTP/1.1\r\nHost: api.github.com\r\n\r\n",
        b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: other.example:443\r\n\r\n",
        b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\nProxy-Authorization: Basic c3ludGhldGlj\r\n\r\n",
        b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\nConnection: upgrade\r\n\r\n",
        b"CONNECT api.github.com:443.evil HTTP/1.1\r\nHost: api.github.com:443.evil\r\n\r\n",
    )
    for index, payload in enumerate(invalid, 1):
        require(rejected(payload), "PROXY_DENIAL_" + str(index))
    print("PROXY_DENIED_REQUESTS=" + str(len(invalid)), flush=True)

    for target, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        require(direct_denied(socket.AF_INET, target, port),
                "CLIENT_DIRECT_IPV4_EGRESS_" + target)
    print("DIRECT_IPV4_DENIAL_SAMPLES=PASS", flush=True)

    require(direct_denied(socket.AF_INET6, "2606:4700:4700::1111", 443),
            "CLIENT_DIRECT_IPV6_EGRESS")
    print("DIRECT_IPV6_DENIAL_SAMPLE=PASS", flush=True)

    # One unauthenticated TLS handshake over an explicit CONNECT tunnel.
    # No GitHub REST endpoint request, model call or customer data.
    with connect_proxy(REQUEST) as conn:
        require(recv_head(conn) == b"HTTP/1.1 200 Connection Established",
                "GITHUB_CONNECT_NOT_ALLOWED")
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        with context.wrap_socket(conn, server_hostname="api.github.com") as tls:
            require(tls.version() in ("TLSv1.2", "TLSv1.3"),
                    "GITHUB_TLS_VERSION")
            cert = tls.getpeercert()
            require(bool(cert), "GITHUB_TLS_CERT_MISSING")
            print("GITHUB_PROXY_TLS_VERIFIED=PASS", flush=True)

    print("GATE_10C18P_NETWORK_ONLY=PASS", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("GATE_10C18P_NETWORK_ONLY=BLOCKED", flush=True)
        print("FAILURE_CLASS=" + type(exc).__name__, flush=True)
        if isinstance(exc, RuntimeError):
            print("FAILURE_CODE=" + str(exc), flush=True)
        sys.exit(2)
