"""Classify a read-only cPanel session without echoing tokens, cookies, or addresses."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

TLS_EXITS = {35, 51, 58, 60, 77}
TRANSPORT_EXITS = {6, 7, 28, 52, 56}
TOKEN_PATTERN = re.compile(r"^/cpsess[0-9A-Za-z]+$")


def format_label(label, cookie_state=""):
    if label == "SESSION_ACCEPTED" and cookie_state in {"present", "absent"}:
        return "SESSION_ACCEPTED\ncookie={0}\n".format(cookie_state)
    return label + "\n"


def _transport_label(http_code, curl_exit):
    code = (http_code or "").strip()
    if curl_exit in TLS_EXITS:
        return "TLS_ERROR"
    if curl_exit in TRANSPORT_EXITS or code in {"", "000"}:
        return "HTTP_TRANSPORT_ERROR"
    if curl_exit != 0 and not (code.isdigit() and len(code) == 3):
        return "HTTP_TRANSPORT_ERROR"
    return ""


def _payload(body):
    stripped = (body or b"").lstrip()
    lowered = stripped[:16].lower()
    if lowered.startswith(b"<!doctype") or lowered.startswith(b"<html"):
        return "html", None
    if not stripped:
        return "other", None
    try:
        return "json", json.loads(stripped.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "other", None


def cookie_has_session(cookie_text):
    if isinstance(cookie_text, bytes):
        cookie_text = cookie_text.decode("utf-8", "replace")
    for raw_line in (cookie_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, _secure, _expires, name, value = parts[:7]
        if domain.strip() and path.strip() and name.strip() and value.strip():
            return True
    return False


def _http_success(http_code):
    code = (http_code or "").strip()
    return len(code) == 3 and code.isdigit() and code.startswith("2")


def diagnose_login(http_code, curl_exit, body, cookie_text):
    cookie_state = "present" if cookie_has_session(cookie_text) else "absent"
    transport = _transport_label(http_code, curl_exit)
    if transport:
        return transport, "", ""
    if not _http_success(http_code):
        return "INVALID_RESPONSE", "", ""
    kind, payload = _payload(body)
    if kind != "json" or not isinstance(payload, dict):
        return "INVALID_RESPONSE", "", ""
    if payload.get("status") != 1:
        return "SESSION_STATUS_REJECTED", "", ""
    raw_token = payload.get("security_token")
    token = raw_token.strip() if isinstance(raw_token, str) else ""
    if not token:
        return "SESSION_TOKEN_ABSENT", "", ""
    if TOKEN_PATTERN.fullmatch(token) is None:
        return "SESSION_TOKEN_INVALID", "", ""
    return "SESSION_ACCEPTED", token, cookie_state


def _whitelist_ok(payload):
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return False
    data = payload.get("data")
    return isinstance(data, dict) and isinstance(data.get("list"), list)


def diagnose_list(http_code, curl_exit, body):
    transport = _transport_label(http_code, curl_exit)
    if transport:
        return transport
    if not _http_success(http_code):
        return "WHITELIST_READ_FAILED"
    kind, payload = _payload(body)
    if kind != "json":
        return "INVALID_RESPONSE"
    if _whitelist_ok(payload):
        return "WHITELIST_READ_OK"
    return "WHITELIST_READ_FAILED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("login", "list"))
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--cookie-file")
    parser.add_argument("--token-file")
    args = parser.parse_args(argv)
    http_code = os.environ.get("CPANEL_HTTP_CODE", "")
    curl_exit = int(os.environ.get("CPANEL_CURL_EXIT", "0"))
    body = Path(args.body_file).read_bytes()
    if args.phase == "login":
        cookie_text = ""
        if args.cookie_file:
            cookie_text = Path(args.cookie_file).read_text(encoding="utf-8", errors="replace")
        label, token, cookie_state = diagnose_login(http_code, curl_exit, body, cookie_text)
        sys.stdout.write(format_label(label, cookie_state))
        if label == "SESSION_ACCEPTED" and args.token_file:
            path = Path(args.token_file)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(token)
            return 0
        return 1
    label = diagnose_list(http_code, curl_exit, body)
    sys.stdout.write(format_label(label))
    if label == "WHITELIST_READ_OK":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
