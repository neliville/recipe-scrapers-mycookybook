"""Classify a read-only cPanel whitelist response without echoing it."""

import argparse
import json
import os
import sys
from pathlib import Path

TLS_EXITS = {35, 51, 58, 60, 77}
TRANSPORT_EXITS = {6, 7, 28, 52, 56}


class Report:
    def __init__(self, cpanel_http, body_kind, json_state, structure, authentication):
        self.cpanel_http = cpanel_http
        self.body_kind = body_kind
        self.json_state = json_state
        self.structure = structure
        self.authentication = authentication


def _http_label(code):
    if code == "200":
        return "HTTP_OK"
    if code == "401":
        return "HTTP_UNAUTHORIZED"
    if code == "403":
        return "HTTP_FORBIDDEN"
    if code == "404":
        return "HTTP_NOT_FOUND"
    if code == "429":
        return "HTTP_TOO_MANY_REQUESTS"
    if code.startswith("5") and len(code) == 3:
        return "HTTP_SERVER_ERROR"
    return "HTTP_OTHER"


def _body_kind(body):
    stripped = body.lstrip()
    lowered = stripped[:16].lower()
    if lowered.startswith(b"<!doctype") or lowered.startswith(b"<html"):
        return "html", None
    if not stripped:
        return "other", None
    try:
        return "json", json.loads(stripped.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "other", None


def _structure_ok(payload):
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    return (
        isinstance(payload.get("success"), bool)
        and isinstance(data, dict)
        and isinstance(data.get("list"), list)
    )


def classify(http_code, curl_exit, body):
    code = (http_code or "").strip()
    if curl_exit in TLS_EXITS:
        label = "TLS_ERROR"
    elif code.isdigit() and len(code) == 3 and code != "000":
        label = _http_label(code)
    elif curl_exit in TRANSPORT_EXITS or code in {"", "000"} or curl_exit != 0:
        label = "HTTP_TRANSPORT"
    else:
        label = "HTTP_OTHER"

    kind, payload = _body_kind(body or b"")
    json_state = "valid" if kind == "json" else "invalid"
    structure = "ok" if kind == "json" and _structure_ok(payload) else "mismatch"
    if label != "HTTP_OK":
        authentication = "not_applicable"
    elif (
        kind == "json"
        and structure == "ok"
        and payload.get("success") is True
    ):
        authentication = "accepted"
    else:
        authentication = "rejected"
    return Report(label, kind, json_state, structure, authentication)


def format_report(report):
    if report.cpanel_http == "TLS_ERROR":
        return "cpanel_http=TLS_ERROR\n"
    lines = [
        "cpanel_http={0}".format(report.cpanel_http),
        "body_kind={0}".format(report.body_kind),
        "json={0}".format(report.json_state),
        "structure={0}".format(report.structure),
        "authentication={0}".format(report.authentication),
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file", required=True)
    args = parser.parse_args(argv)
    http_code = os.environ.get("CPANEL_HTTP_CODE", "")
    curl_exit = int(os.environ.get("CPANEL_CURL_EXIT", "0"))
    body = Path(args.body_file).read_bytes()
    report = classify(http_code, curl_exit, body)
    sys.stdout.write(format_report(report))
    if report.authentication == "accepted":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
