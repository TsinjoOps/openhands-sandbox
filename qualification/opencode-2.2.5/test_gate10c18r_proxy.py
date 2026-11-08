#!/usr/bin/env python3
"""Gate 10C.18r: offline parse test for one-tunnel synthetic-only CONNECT relay."""
import unittest
import gate10c18r_connect_proxy as relay

BASE = b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\n"

class SyntheticConnectTests(unittest.TestCase):
    def test_allowed_minimal_and_go_client(self):
        self.assertTrue(relay.allowed(BASE + b"\r\n"))
        self.assertTrue(relay.allowed(
            BASE + b"User-Agent: Go-http-client/1.1\r\n\r\n"))
        self.assertTrue(relay.allowed(
            BASE + b"Proxy-Connection: Keep-Alive\r\nUser-Agent: Go-http-client/1.1\r\n\r\n"))

    def test_rejected_unapproved_requests(self):
        samples = [
            b"CONNECT other.example:443 HTTP/1.1\r\nHost: other.example:443\r\n\r\n",
            b"CONNECT api.github.com:80 HTTP/1.1\r\nHost: api.github.com:80\r\n\r\n",
            BASE + b"Proxy-Authorization: Basic c3ludGhldGlj\r\n\r\n",
            BASE + b"User-Agent: synthetic-other-agent\r\n\r\n",
            BASE + b"X-Forwarded-Host: other.example\r\n\r\n",
            BASE + b"Host: api.github.com:443\r\n\r\n",
            BASE + b"\r\ntrailing",
            BASE.replace(b"\r\n", b"\n") + b"\n",
            BASE + b"Connection: upgrade\r\n\r\n",
            b"GET https://api.github.com/ HTTP/1.1\r\nHost: api.github.com\r\n\r\n",
            BASE + b"\xff\r\n\r\n",
            b"",
            b"x" * 5000,
        ]
        for value in samples:
            with self.subTest(value="denied"):
                self.assertFalse(relay.allowed(value))

    def test_exact_tunnel_policy(self):
        self.assertEqual(relay.HOST, "api.github.com")
        self.assertEqual(relay.PORT, 443)
        self.assertEqual(relay.LISTEN_PORT, 3128)
        self.assertLessEqual(relay.MAX_BYTES, 512 * 1024)
        self.assertLessEqual(relay.DEADLINE_SEC, 15)

if __name__ == "__main__":
    unittest.main()
