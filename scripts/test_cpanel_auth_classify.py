"""Simulated responses for the read-only cPanel whitelist diagnostic."""

import json
import unittest
from pathlib import Path

import yaml

import cpanel_auth_classify as diag

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cpanel-auth-check.yml"
FAKE_IP = "203.0.113.50"
MARKER = "NOT-A-SECRET-MARKER"


def report(http_code, body, curl_exit=0):
    if isinstance(body, str):
        body = body.encode()
    return diag.format_report(diag.classify(http_code, curl_exit, body))


def assert_safe(test, text, *forbidden):
    for item in forbidden:
        test.assertNotIn(item, text)


class ClassifyTests(unittest.TestCase):
    def test_successful_authentication(self):
        body = json.dumps(
            {
                "success": True,
                "data": {
                    "ip": FAKE_IP,
                    "count": 1,
                    "list": [
                        {
                            "address": FAKE_IP,
                            "direction": "in",
                            "port": 22,
                            "updateDate": "22/11/2026",
                        }
                    ],
                },
            }
        )
        text = report("200", body)
        self.assertIn("cpanel_http=HTTP_OK", text)
        self.assertIn("body_kind=json", text)
        self.assertIn("json=valid", text)
        self.assertIn("structure=ok", text)
        self.assertIn("authentication=accepted", text)
        assert_safe(self, text, "200", FAKE_IP, MARKER)

    def test_rejected_credentials(self):
        text = report("401", f"<html><title>Identifiant cPanel</title>{MARKER}</html>", 0)
        self.assertIn("cpanel_http=HTTP_UNAUTHORIZED", text)
        self.assertIn("body_kind=html", text)
        self.assertIn("authentication=not_applicable", text)
        assert_safe(self, text, "401", MARKER, "Identifiant")

    def test_html_login_page_on_http_success(self):
        text = report(
            "200",
            f"<!DOCTYPE html><html><title>Identifiant cPanel</title>{FAKE_IP}</html>",
        )
        self.assertIn("cpanel_http=HTTP_OK", text)
        self.assertIn("body_kind=html", text)
        self.assertIn("json=invalid", text)
        self.assertIn("authentication=rejected", text)
        assert_safe(self, text, "200", FAKE_IP, "Identifiant", "<html")

    def test_forbidden(self):
        text = report("403", "Access denied")
        self.assertIn("cpanel_http=HTTP_FORBIDDEN", text)
        assert_safe(self, text, "403", "Access denied")

    def test_not_found(self):
        text = report("404", "missing")
        self.assertIn("cpanel_http=HTTP_NOT_FOUND", text)
        assert_safe(self, text, "404", "missing")

    def test_too_many_requests(self):
        text = report("429", "slow down")
        self.assertIn("cpanel_http=HTTP_TOO_MANY_REQUESTS", text)
        assert_safe(self, text, "429", "slow down")

    def test_server_error(self):
        text = report("503", "unavailable")
        self.assertIn("cpanel_http=HTTP_SERVER_ERROR", text)
        assert_safe(self, text, "503", "500", "unavailable")

    def test_tls_error(self):
        text = report("000", b"", curl_exit=60)
        self.assertIn("cpanel_http=TLS_ERROR", text)
        assert_safe(self, text, "60", "000", "HTTP_TRANSPORT")

    def test_network_timeout(self):
        text = report("000", b"", curl_exit=28)
        self.assertIn("cpanel_http=HTTP_TRANSPORT", text)
        assert_safe(self, text, "28", "000")

    def test_invalid_json(self):
        text = report("200", "{not-json")
        self.assertIn("cpanel_http=HTTP_OK", text)
        self.assertIn("json=invalid", text)
        self.assertIn("body_kind=other", text)
        self.assertIn("authentication=rejected", text)
        assert_safe(self, text, "200", "{not-json")

    def test_business_failure_is_not_accepted(self):
        body = json.dumps({"success": False, "message": MARKER, "data": {"list": []}})
        text = report("200", body)
        self.assertIn("authentication=rejected", text)
        self.assertNotIn("authentication=accepted", text)
        assert_safe(self, text, MARKER)


class WorkflowContractTests(unittest.TestCase):
    def test_workflow_is_push_only_and_read_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ci/cpanel-auth-check", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("workflow_dispatch", text)
        self.assertNotIn("develop", text)
        self.assertNotIn("main", text)
        self.assertNotIn("r=add", text)
        self.assertNotIn("r=remove", text)
        self.assertNotIn("appleboy/ssh-action", text)
        self.assertNotIn("--insecure", text)
        self.assertNotIn("ACTIONS_STEP_DEBUG", text)
        self.assertNotIn("-k", text)
        self.assertNotIn("--verbose", text)
        self.assertNotIn("curl -v", text)
        self.assertIn("r=list", text)
        self.assertIn("secrets.O2SWITCH_CPANEL_HOST", text)
        self.assertNotIn("secrets.O2SWITCH_HOST", text)
        self.assertNotIn("odns.fr", text)
        self.assertNotIn("o2switch.net", text)
        self.assertIn("O2SWITCH_USER", text)
        self.assertIn("O2SWITCH_CPANEL_PASSWORD", text)
        self.assertIn("rm -f", text)

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
