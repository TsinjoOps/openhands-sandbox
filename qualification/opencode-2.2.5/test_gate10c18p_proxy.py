#!/usr/bin/env python3
"""Pure offline parser tests for the 10C.18p throwaway CONNECT proxy."""
import unittest
import gate10c18p_connect_proxy as relay

GOOD = b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\n\r\n"

class ConnectPolicyTests(unittest.TestCase):
    def test_exact_positive_authority(self):
        self.assertTrue(relay.allowed(GOOD))
        self.assertTrue(relay.allowed(
            b"CONNECT api.github.com:443 HTTP/1.1\r\n"
            b"Host: api.github.com:443\r\nProxy-Connection: Keep-Alive\r\n\r\n"
        ))

    def test_deny_host_port_method_and_credentials(self):
        denied = (
            b"CONNECT example.org:443 HTTP/1.1\r\nHost: example.org:443\r\n\r\n",
            b"CONNECT api.github.com:80 HTTP/1.1\r\nHost: api.github.com:80\r\n\r\n",
            b"CONNECT 1.1.1.1:443 HTTP/1.1\r\nHost: 1.1.1.1:443\r\n\r\n",
            b"GET http://api.github.com HTTP/1.1\r\nHost: api.github.com\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: alt.test:443\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\nProxy-Authorization: Basic c3ludGhldGlj\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\nConnection: upgrade\r\n\r\n",
            b"CONNECT api.github.com:443.evil HTTP/1.1\r\nHost: api.github.com:443.evil\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.0\r\nHost: api.github.com:443\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.1\r\n\r\n",
            b"CONNECT api.github.com:443 HTTP/1.1\r\nHost: api.github.com:443\r\nHost: api.github.com:443\r\n\r\n",
            GOOD + b"\x00more",
            GOOD[:-4],
            GOOD.replace(b"\r\n", b"\n"),
            b"\xff" + GOOD,
            b"",
            b"X" * 5000,
        )
        for candidate in denied:
            with self.subTest(case="invalid"):
                self.assertFalse(relay.allowed(candidate))

    def test_limits_and_scope_are_explicit(self):
        self.assertEqual(relay.HOST, "api.github.com")
        self.assertEqual(relay.PORT, 443)
        self.assertEqual(relay.LISTEN_PORT, 3128)
        self.assertLessEqual(relay.MAX_BYTES, 1024 * 1024)
        self.assertLessEqual(relay.DEADLINE_SEC, 15)
        self.assertFalse(relay.allowed("not bytes"))

if __name__ == "__main__":
    unittest.main(verbosity=0)
