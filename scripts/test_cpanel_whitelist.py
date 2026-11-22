"""Simulated cPanel session and whitelist decisions for the staging deploy."""

import json
import unittest
from pathlib import Path

import cpanel_auth_classify as diag

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-staging.yml"
TOKEN = "/cpsessTESTTOKEN"
RUNNER = "203.0.113.10"
PROTECTED = "198.51.100.20"
STALE = "203.0.113.30"
HTTPONLY = "#HttpOnly_.example.test\tTRUE\t/\tTRUE\t0\tcpsession\tsecretvalue\n"


def login(body, http_code="200", curl_exit=0, cookie=HTTPONLY):
    if isinstance(body, str):
        body = body.encode()
    label, token, cookie_state = diag.diagnose_login(http_code, curl_exit, body, cookie)
    return diag.format_label(label, cookie_state), token


def entries(*addresses):
    rows = []
    for address in addresses:
        rows.append({"address": address, "direction": "in", "port": 22})
        rows.append({"address": address, "direction": "out", "port": 22})
    return rows


class SessionTests(unittest.TestCase):
    def test_valid_session_with_httponly_cookie(self):
        text, token = login(json.dumps({"status": 1, "security_token": TOKEN}))
        self.assertIn("SESSION_ACCEPTED", text)
        self.assertIn("cookie=present", text)
        self.assertEqual(token, TOKEN)
        self.assertNotIn("secretvalue", text)
        self.assertNotIn(TOKEN, text)

    def test_session_rejected(self):
        text, token = login(json.dumps({"status": 0, "message": "nope"}))
        self.assertIn("SESSION_STATUS_REJECTED", text)
        self.assertEqual(token, "")
        self.assertNotIn("nope", text)

    def test_token_absent_or_invalid(self):
        absent, token = login(json.dumps({"status": 1}))
        self.assertIn("SESSION_TOKEN_ABSENT", absent)
        self.assertEqual(token, "")
        invalid, token = login(json.dumps({"status": 1, "security_token": "/cpsessOK/../x"}))
        self.assertIn("SESSION_TOKEN_INVALID", invalid)
        self.assertEqual(token, "")
        self.assertNotIn("../", invalid)

    def test_tls_and_timeout(self):
        text, _token = login(b"", http_code="000", curl_exit=60, cookie="")
        self.assertIn("TLS_ERROR", text)
        self.assertIn("HTTP_TRANSPORT_ERROR", diag.diagnose_list("000", 28, b""))


class WhitelistPlanTests(unittest.TestCase):
    def test_list_shape_is_readable(self):
        body = json.dumps({"success": True, "data": {"list": entries(RUNNER)}})
        self.assertEqual(diag.diagnose_list("200", 0, body.encode()), "WHITELIST_READ_OK")

    def test_already_authorized_makes_no_change(self):
        plan = diag.plan_whitelist(entries(PROTECTED, RUNNER), RUNNER, PROTECTED)
        self.assertEqual(plan["action"], "already_present")
        self.assertEqual(plan["remove"], [])

    def test_add_when_quota_has_room(self):
        plan = diag.plan_whitelist(entries(PROTECTED), RUNNER, PROTECTED)
        self.assertEqual(plan["action"], "add")
        self.assertEqual(plan["remove"], [])

    def test_protected_address_is_never_removed(self):
        full = entries(PROTECTED, STALE, "203.0.113.40", "203.0.113.50", "203.0.113.60")
        plan = diag.plan_whitelist(full, RUNNER, PROTECTED)
        self.assertEqual(plan["action"], "prune_then_add")
        removed = {row["address"] for row in plan["remove"]}
        self.assertNotIn(PROTECTED, removed)
        self.assertNotIn(RUNNER, removed)
        self.assertTrue(removed)
        self.assertTrue(all(row["direction"] in {"in", "out"} for row in plan["remove"]))

    def test_quota_blocked_when_only_protected_addresses_remain(self):
        full = entries(
            PROTECTED,
            "198.51.100.21",
            "198.51.100.22",
            "198.51.100.23",
            "198.51.100.24",
        )
        plan = diag.plan_whitelist(full, RUNNER, ",".join(address for address in (
            PROTECTED, "198.51.100.21", "198.51.100.22", "198.51.100.23", "198.51.100.24",
        )))
        self.assertEqual(plan["action"], "quota_blocked")
        self.assertEqual(plan["remove"], [])

    def test_add_refused_and_delete_failure(self):
        refused = json.dumps({"success": False, "message": "denied"}).encode()
        self.assertEqual(diag.diagnose_mutation("200", 0, refused), "WHITELIST_MUTATION_FAILED")
        quota = json.dumps({"success": False, "message": "limite d'exceptions atteinte"}).encode()
        self.assertEqual(diag.diagnose_mutation("200", 0, quota), "QUOTA_REACHED")

    def test_invalid_json(self):
        self.assertEqual(diag.diagnose_list("200", 0, b"{not-json"), "INVALID_RESPONSE")
        self.assertEqual(diag.diagnose_mutation("200", 0, b"{not-json"), "INVALID_RESPONSE")

    def test_confirm_requires_runner(self):
        present = json.dumps({"success": True, "data": {"list": entries(RUNNER)}}).encode()
        absent = json.dumps({"success": True, "data": {"list": entries(PROTECTED)}}).encode()
        self.assertEqual(diag.confirm_runner("200", 0, present, RUNNER, "22"), "WHITELIST_CONFIRMED")
        self.assertEqual(diag.confirm_runner("200", 0, absent, RUNNER, "22"), "WHITELIST_UNCONFIRMED")
        self.assertNotIn(RUNNER, "WHITELIST_UNCONFIRMED")


class WorkflowContractTests(unittest.TestCase):
    def test_ssh_cannot_start_before_whitelist_confirmation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        confirm_at = text.index("Confirm runner whitelist")
        ssh_at = text.index("appleboy/ssh-action")
        self.assertLess(confirm_at, ssh_at)
        self.assertIn("contents: read", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("login_only=1", text)
        self.assertIn("secrets.O2SWITCH_CPANEL_HOST", text)
        self.assertIn("secrets.O2SWITCH_HOST", text)
        self.assertIn("O2SWITCH_KEEP_IPS", text)
        self.assertIn("chmod 600", text)
        self.assertNotIn("curl -k", text)
        self.assertNotIn("--insecure", text)
        self.assertNotIn("--user", text)
        self.assertNotIn("|| true", text)
        self.assertNotIn("head -c", text)
        self.assertNotIn("sleep 65", text)


if __name__ == "__main__":
    unittest.main()
