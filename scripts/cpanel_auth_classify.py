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


def _keep_set(keep_ips):
    if isinstance(keep_ips, str):
        parts = keep_ips.split(",")
    else:
        parts = list(keep_ips)
    return {part.strip() for part in parts if part and part.strip()}


def _ipv4(value):
    text = str(value or "")
    pieces = text.split(".")
    if len(pieces) != 4:
        return False
    for piece in pieces:
        if not piece.isdigit() or piece != str(int(piece)):
            return False
        if int(piece) > 255:
            return False
    return True


def _port_rows(entries, ssh_port):
    port = str(ssh_port)
    rows = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        address = str(item.get("address") or "")
        direction = str(item.get("direction") or "")
        if str(item.get("port", "")) != port:
            continue
        if direction not in {"in", "out"} or not _ipv4(address):
            continue
        rows.append({"address": address, "direction": direction})
    return rows


def _unique(rows):
    seen = []
    for row in rows:
        if row["address"] not in seen:
            seen.append(row["address"])
    return seen


def plan_whitelist(entries, runner_ip, keep_ips, ssh_port="22", quota=5):
    """Decide whether the runner can be added without deleting any address.

    An address absent from O2SWITCH_KEEP_IPS is not evidence that it is an old
    runner. Manual SSH exceptions are indistinguishable from them, so this
    first staging deploy never removes a whitelist row.
    """
    if not _ipv4(runner_ip):
        return {"action": "invalid_runner", "remove": [], "manual_cleanup_required": False}
    _keep_set(keep_ips)
    rows = _port_rows(entries, ssh_port)
    if any(row["address"] == runner_ip for row in rows):
        return {"action": "already_present", "remove": [], "manual_cleanup_required": False}
    if len(_unique(rows)) < quota:
        return {"action": "add", "remove": [], "manual_cleanup_required": False}
    return {"action": "quota_blocked", "remove": [], "manual_cleanup_required": True}


def diagnose_mutation(http_code, curl_exit, body):
    transport = _transport_label(http_code, curl_exit)
    if transport:
        return transport
    if not _http_success(http_code):
        return "WHITELIST_MUTATION_FAILED"
    kind, payload = _payload(body)
    if kind != "json" or not isinstance(payload, dict):
        return "INVALID_RESPONSE"
    if payload.get("success") is True:
        return "WHITELIST_MUTATION_OK"
    if "limite" in str(payload.get("message") or "").lower():
        return "QUOTA_REACHED"
    return "WHITELIST_MUTATION_FAILED"


def confirm_runner(http_code, curl_exit, body, runner_ip, ssh_port):
    if diagnose_list(http_code, curl_exit, body) != "WHITELIST_READ_OK":
        return diagnose_list(http_code, curl_exit, body)
    _kind, payload = _payload(body)
    rows = _port_rows(payload["data"]["list"], ssh_port)
    if any(row["address"] == runner_ip for row in rows):
        return "WHITELIST_CONFIRMED"
    return "WHITELIST_UNCONFIRMED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("login", "list", "plan", "mutation", "confirm"))
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--cookie-file")
    parser.add_argument("--token-file")
    parser.add_argument("--remove-file")
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
    if args.phase == "plan":
        listed = diagnose_list(http_code, curl_exit, body)
        if listed != "WHITELIST_READ_OK":
            sys.stdout.write(format_label(listed))
            return 1
        _kind, payload = _payload(body)
        plan = plan_whitelist(
            payload["data"]["list"],
            os.environ.get("CPANEL_RUNNER_IP", ""),
            os.environ.get("CPANEL_KEEP_IPS", ""),
            os.environ.get("CPANEL_SSH_PORT", "22"),
        )
        if args.remove_file:
            path = Path(args.remove_file)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                for row in plan["remove"]:
                    handle.write("{0}\t{1}\n".format(row["address"], row["direction"]))
        sys.stdout.write("action={0}\n".format(plan["action"]))
        if plan["manual_cleanup_required"]:
            sys.stdout.write("manual_cleanup_required\n")
        return 0 if plan["action"] in {"already_present", "add"} else 1
    if args.phase == "mutation":
        label = diagnose_mutation(http_code, curl_exit, body)
        sys.stdout.write(format_label(label))
        return 0 if label == "WHITELIST_MUTATION_OK" else 1
    if args.phase == "confirm":
        label = confirm_runner(
            http_code,
            curl_exit,
            body,
            os.environ.get("CPANEL_RUNNER_IP", ""),
            os.environ.get("CPANEL_SSH_PORT", "22"),
        )
        sys.stdout.write(format_label(label))
        return 0 if label == "WHITELIST_CONFIRMED" else 1
    label = diagnose_list(http_code, curl_exit, body)
    sys.stdout.write(format_label(label))
    if label == "WHITELIST_READ_OK":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
