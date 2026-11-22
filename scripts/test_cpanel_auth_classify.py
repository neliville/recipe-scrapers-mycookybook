"""Simulated cPanel session responses. Reports must not echo secrets or addresses."""

import json
import unittest
from pathlib import Path

import yaml

import cpanel_auth_classify as diag

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cpanel-auth-check.yml"
FAKE_IP = "203.0.113.50"
MARKER = "NOT-A-SECRET-MARKER"
TOKEN = "/cpsessTESTTOKEN"
COOKIE = ".example.test\tTRUE\t/\tTRUE\t0\tsession\tvalue\n"


def login_report(http_code, body, curl_exit=0, cookie=COOKIE):
    if isinstance(body, str):
        body = body.encode()
    label, token = diag.diagnose_login(http_code, curl_exit, body, cookie)
    text = diag.format_label(label)
    return text, token


def list_report(http_code, body, curl_exit=0):
    if isinstance(body, str):
        body = body.encode()
    label = diag.diagnose_list(http_code, curl_exit, body)
    return diag.format_label(label)


def assert_safe(test, text, *forbidden):
    for item in forbidden:
        test.assertNotIn(item, text)


class SessionTests(unittest.TestCase):
    def test_session_accepted(self):
        body = json.dumps({"status": 1, "security_token": TOKEN})
        text, token = login_report("200", body)
        self.assertIn("SESSION_ACCEPTED", text)
        self.assertEqual(token, TOKEN)
        assert_safe(self, text, TOKEN, "200", MARKER)

    def test_wrong_password(self):
        body = json.dumps({"status": 0, "message": MARKER})
        text, token = login_report("200", body)
        self.assertIn("SESSION_REJECTED", text)
        self.assertEqual(token, "")
        self.assertNotIn("SESSION_ACCEPTED", text)
        assert_safe(self, text, MARKER, "200")

    def test_missing_cookie(self):
        body = json.dumps({"status": 1, "security_token": TOKEN})
        text, token = login_report("200", body, cookie="")
        self.assertIn("SESSION_REJECTED", text)
        self.assertEqual(token, "")
        assert_safe(self, text, TOKEN)

    def test_missing_security_token(self):
        body = json.dumps({"status": 1, "security_token": ""})
        text, token = login_report("200", body)
        self.assertIn("SESSION_REJECTED", text)
        self.assertEqual(token, "")

    def test_expired_session_returns_html(self):
        text = list_report(
            "200",
            "<!DOCTYPE html><html><title>Identifiant cPanel</title>{0}</html>".format(FAKE_IP),
        )
        self.assertIn("INVALID_RESPONSE", text)
        self.assertNotIn("WHITELIST_READ_OK", text)
        assert_safe(self, text, FAKE_IP, "Identifiant", "<html", "200")

    def test_tls_error(self):
        text, token = login_report("000", b"", curl_exit=60, cookie="")
        self.assertIn("TLS_ERROR", text)
        self.assertEqual(token, "")
        assert_safe(self, text, "60", "000", "SESSION_ACCEPTED")

    def test_timeout(self):
        text = list_report("000", b"", curl_exit=28)
        self.assertIn("HTTP_TRANSPORT_ERROR", text)
        assert_safe(self, text, "28", "000")

    def test_http_error(self):
        text = list_report("503", "unavailable")
        self.assertIn("WHITELIST_READ_FAILED", text)
        assert_safe(self, text, "503", "500", "unavailable")

    def test_whitelist_read_ok_hides_addresses(self):
        body = json.dumps(
            {
                "success": True,
                "data": {
                    "ip": FAKE_IP,
                    "count": 1,
                    "list": [{"address": FAKE_IP, "direction": "in", "port": 22}],
                },
            }
        )
        text = list_report("200", body)
        self.assertIn("WHITELIST_READ_OK", text)
        assert_safe(self, text, FAKE_IP, "200")

    def test_business_failure(self):
        body = json.dumps({"success": False, "message": MARKER, "data": {"list": []}})
        text = list_report("200", body)
        self.assertIn("WHITELIST_READ_FAILED", text)
        self.assertNotIn("WHITELIST_READ_OK", text)
        assert_safe(self, text, MARKER)


class WorkflowContractTests(unittest.TestCase):
    def test_workflow_is_push_only_and_read_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ci/cpanel-auth-check", text)
        self.assertIn("contents: read", text)
        self.assertIn("login_only=1", text)
        self.assertIn("r=list", text)
        self.assertIn("chmod 600", text)
        self.assertIn("secrets.O2SWITCH_CPANEL_HOST", text)
        self.assertIn("O2SWITCH_USER", text)
        self.assertIn("O2SWITCH_CPANEL_PASSWORD", text)
        self.assertIn("rm -f", text)
        self.assertNotIn("workflow_dispatch", text)
        self.assertNotIn("develop", text)
        self.assertNotIn("main", text)
        self.assertNotIn("r=add", text)
        self.assertNotIn("r=remove", text)
        self.assertNotIn("appleboy/ssh-action", text)
        self.assertNotIn("deploy-staging", text)
        self.assertNotIn("--insecure", text)
        self.assertNotIn("ACTIONS_STEP_DEBUG", text)
        self.assertNotIn("-k", text)
        self.assertNotIn("--verbose", text)
        self.assertNotIn("curl -v", text)
        self.assertNotIn("--user", text)
        self.assertNotIn("secrets.O2SWITCH_HOST", text)
        self.assertNotIn("odns.fr", text)
        self.assertNotIn("o2switch.net", text)

    def test_workflow_yaml_parses(self):
        data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        trigger = data.get("on", data.get(True))
        self.assertIsInstance(trigger, dict)
        self.assertEqual(list(trigger), ["push"])
        self.assertEqual(trigger["push"]["branches"], ["ci/cpanel-auth-check"])
        self.assertEqual(data["permissions"], {"contents": "read"})
        self.assertNotIn("pull_request", trigger)


if __name__ == "__main__":
    unittest.main()
