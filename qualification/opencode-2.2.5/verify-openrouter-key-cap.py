#!/usr/bin/env python3
"""Gate 10C.18: verify a dedicated OpenRouter API key cap without revealing the key.

--self-test is fully offline. --key-file performs one HTTPS GET to
https://openrouter.ai/api/v1/key. Never run --key-file before approving egress.
No model inference, token output, redirects or automatic retries.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import ssl
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

ENDPOINT = "https://openrouter.ai/api/v1/key"
LATEST_EXPIRY = datetime(2026, 11, 15, tzinfo=timezone.utc)
MAX_RESPONSE = 16384


def admission(data, now):
    """Return a safe reason code. Do not return the raw server response."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        return "INVALID_RESPONSE"
    info = data["data"]
    limit = info.get("limit")
    remaining = info.get("limit_remaining")
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit != 2:
        return "LIMIT_NOT_2_USD"
    if (isinstance(remaining, bool) or not isinstance(remaining, (int, float))
            or not 0 <= remaining <= 2):
        return "REMAINING_INVALID"
    if info.get("limit_reset", "MISSING") is not None:
        return "RESET_NOT_DISABLED"
    if info.get("is_management_key") is not False:
        return "MANAGEMENT_KEY_NOT_EXCLUDED"
    if info.get("is_provisioning_key") is not False:
        return "PROVISIONING_KEY_NOT_EXCLUDED"
    raw_expiry = info.get("expires_at")
    if not isinstance(raw_expiry, str):
        return "EXPIRY_MISSING"
    try:
        expiry = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
    except ValueError:
        return "EXPIRY_INVALID"
    if expiry.tzinfo is None or not now < expiry <= LATEST_EXPIRY:
        return "EXPIRY_OUT_OF_RANGE"
    return "PASS"


def key_from_file(filename):
    """Open without symlink following, enforce a private file owned by caller."""
    path = Path(filename)
    if not path.is_absolute():
        raise ValueError("KEY_PATH_NOT_ABSOLUTE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode)
                or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077
                or meta.st_nlink != 1
                or meta.st_size > 512):
            raise ValueError("KEY_FILE_PERMISSIONS")
        with os.fdopen(os.dup(fd), "rb") as f:
            secret = f.read(513).strip()
        if not 16 <= len(secret) <= 512 or any(ch <= 32 or ch >= 127 for ch in secret):
            raise ValueError("KEY_VALUE_INVALID")
        return secret.decode("ascii")
    finally:
        os.close(fd)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("REDIRECT_REJECTED")


def online(key):
    request = Request(ENDPOINT, headers={
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
    }, method="GET")
    # Do not silently trust an inherited proxy from the host environment.
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    with opener.open(request, timeout=12) as result:
        if result.status != 200:
            raise ValueError("HTTP_NOT_200")
        raw = result.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("RESPONSE_TOO_LARGE")
    return json.loads(raw)


def self_test():
    valid = {"data": {
        "limit": 2.0, "limit_remaining": 1.9, "limit_reset": None,
        "is_management_key": False, "is_provisioning_key": False,
        "expires_at": "2026-11-13T00:00:00Z",
    }}
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    assert admission(valid, now) == "PASS"
    cases = [
        ({"limit": None}, "LIMIT_NOT_2_USD"),
        ({"limit": 20}, "LIMIT_NOT_2_USD"),
        ({"limit_remaining": -1}, "REMAINING_INVALID"),
        ({"limit_reset": "daily"}, "RESET_NOT_DISABLED"),
        ({"is_management_key": True}, "MANAGEMENT_KEY_NOT_EXCLUDED"),
        ({"is_provisioning_key": True}, "PROVISIONING_KEY_NOT_EXCLUDED"),
        ({"expires_at": None}, "EXPIRY_MISSING"),
        ({"expires_at": "2026-11-14T16:38:00Z"}, "PASS"),
        ({"expires_at": "2026-11-15T00:00:01Z"}, "EXPIRY_OUT_OF_RANGE"),
        ({"expires_at": "2026-11-06T00:00:00Z"}, "EXPIRY_OUT_OF_RANGE"),
        ({"expires_at": "bad"}, "EXPIRY_INVALID"),
    ]
    for override, expected in cases:
        sample = {"data": {**valid["data"], **override}}
        assert admission(sample, now) == expected, expected
    print("OPENROUTER_KEY_POLICY_SELF_TEST=PASS")
    print("OFFLINE_TEST_CASES=12")
    print("NETWORK_REQUEST=NO")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--key-file")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        key = key_from_file(args.key_file)
        record = online(key)
        reason = admission(record, datetime.now(timezone.utc))
    except HTTPError as exc:
        reason = "HTTP_" + str(exc.code)
    except (OSError, ValueError, URLError, json.JSONDecodeError):
        reason = "NETWORK_OR_INPUT_BLOCKED"
    # Never print raw key, headers, API response, key label or token-related paths.
    print("OPENROUTER_KEY_ADMISSION=" + reason)
    print("INFERENCE_CALLS=0")
    return 0 if reason == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
