"""Contrats HTTP de l'API Flask, sans réseau et sans modifier les réponses."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from mycookybook_api.app import app

FIXTURES = Path(__file__).parent / "fixtures"
RECIPE_URL = "https://example.test/tarte"
PARTIAL_URL = "https://example.test/partial"
EMPTY_URL = "https://example.test/vide"

STABLE_SCRAPE_KEYS = {
    "title",
    "ingredients",
    "instructions",
    "image",
    "host",
    "total_time",
    "yields",
    "canonical_url",
}
PARSED_INGREDIENT_KEYS = {"raw", "ingredient", "quantity", "unit", "note"}


def _response(html):
    response = Mock()
    response.text = html
    response.raise_for_status = Mock()
    return response


class HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.pages = {
            RECIPE_URL: (FIXTURES / "schema_recipe.html").read_text(encoding="utf-8"),
            PARTIAL_URL: (FIXTURES / "schema_partial.html").read_text(encoding="utf-8"),
            EMPTY_URL: (FIXTURES / "page_without_recipe.html").read_text(encoding="utf-8"),
        }

    def _get(self, url, timeout=20, headers=None):
        html = self.pages.get(url)
        if html is None:
            raise AssertionError(f"URL de fixture inattendue: {url}")
        return _response(html)

    def test_home_lists_existing_routes(self):
        response = self.client.get("/")
        body = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"service", "version", "endpoints"},
            set(body),
        )
        self.assertIn("/scrape", body["endpoints"])
        self.assertIn("/parse-ingredient", body["endpoints"])
        self.assertIn("/parse-ingredients", body["endpoints"])
        self.assertNotIn("/health", body["endpoints"])

    def test_health_route_is_absent(self):
        response = self.client.get("/health")
        self.assertEqual(404, response.status_code)

    def test_scrape_requires_web_url(self):
        response = self.client.get("/scrape")
        body = response.get_json()

        self.assertEqual(400, response.status_code)
        self.assertFalse(body["success"])
        self.assertEqual("Missing parameter webUrl", body["message"])
        self.assertEqual({}, body["data"])

    def test_scrape_v2_requires_web_url(self):
        response = self.client.get("/scrape-v2")
        body = response.get_json()

        self.assertEqual(400, response.status_code)
        self.assertFalse(body["success"])
        self.assertEqual("Missing webUrl", body["message"])
        self.assertNotIn("data", body)

    def test_scrape_local_fixture_keeps_json_contract(self):
        with patch("mycookybook_api.app.requests.get", side_effect=self._get):
            response = self.client.get(
                "/scrape",
                query_string={"webUrl": RECIPE_URL, "parse_ingredients": "true", "language": "fr"},
            )
        body = response.get_json()
        data = body["data"]

        self.assertEqual(200, response.status_code)
        self.assertTrue(body["success"])
        self.assertEqual("Success", body["message"])
        self.assertTrue(STABLE_SCRAPE_KEYS <= set(data))
        self.assertEqual("Tarte aux pommes", data["title"])
        self.assertEqual(["200 g de farine", "2 oeufs"], data["ingredients"])
        self.assertEqual("Mélanger puis cuire.", data["instructions"])
        self.assertEqual("https://example.test/tarte.jpg", data["image"])
        self.assertEqual(30, data["total_time"])
        self.assertEqual("4", data["yields"])
        self.assertEqual(
            [{"ingredients": ["200 g de farine", "2 oeufs"], "purpose": None}],
            data["ingredient_groups"],
        )
        self.assertNotIn("notes", data)
        self.assertIn("description", data)
        self.assertNotIn("cooking_method", data)
        self.assertEqual(data["ingredients"], data["ingredients_raw"])
        self.assertEqual(2, len(data["ingredients_parsed"]))
        for item in data["ingredients_parsed"]:
            self.assertEqual(PARSED_INGREDIENT_KEYS, set(item))
        self.assertEqual("200 g de farine", data["ingredients_parsed"][0]["raw"])

    def test_scrape_post_accepts_json_body(self):
        with patch("mycookybook_api.app.requests.get", side_effect=self._get):
            response = self.client.post(
                "/scrape",
                json={"webUrl": RECIPE_URL, "parse_ingredients": False},
            )
        data = response.get_json()["data"]

        self.assertEqual(200, response.status_code)
        self.assertNotIn("ingredients_parsed", data)
        self.assertIn("ingredients", data)

    def test_scrape_partial_recipe_returns_422(self):
        with patch("mycookybook_api.app.requests.get", side_effect=self._get):
            response = self.client.get("/scrape", query_string={"webUrl": PARTIAL_URL})
        body = response.get_json()

        self.assertEqual(422, response.status_code)
        self.assertFalse(body["success"])
        self.assertEqual("No recipe data extracted from URL", body["message"])
        self.assertNotIn("title", body["data"])
        self.assertNotIn("ingredients", body["data"])
        self.assertEqual("Seulement une description", body["data"]["description"])
        self.assertEqual(
            [{"ingredients": [], "purpose": None}],
            body["data"]["ingredient_groups"],
        )

    def test_scrape_without_schema_returns_500(self):
        with patch("mycookybook_api.app.requests.get", side_effect=self._get):
            response = self.client.get("/scrape", query_string={"webUrl": EMPTY_URL})
        body = response.get_json()

        self.assertEqual(500, response.status_code)
        self.assertFalse(body["success"])
        self.assertIn("No Recipe Schema found", body["message"])
        self.assertEqual({}, body["data"])

    def test_scrape_timeout_returns_500(self):
        with patch(
            "mycookybook_api.app.requests.get",
            side_effect=requests.Timeout("delai depasse"),
        ):
            response = self.client.get("/scrape", query_string={"webUrl": RECIPE_URL})
        body = response.get_json()

        self.assertEqual(500, response.status_code)
        self.assertFalse(body["success"])
        self.assertIn("delai depasse", body["message"])
        self.assertEqual({}, body["data"])

    def test_scrape_v2_local_fixture(self):
        with patch("mycookybook_api.app.requests.get", side_effect=self._get):
            response = self.client.get("/scrape-v2", query_string={"webUrl": RECIPE_URL})
        body = response.get_json()
        data = body["data"]

        self.assertEqual(200, response.status_code)
        self.assertTrue(body["success"])
        self.assertEqual({"success", "data"}, set(body))
        self.assertEqual("Tarte aux pommes", data["title"])
        self.assertEqual(["200 g de farine", "2 oeufs"], data["ingredients"])
        self.assertEqual("Mélanger puis cuire.", data["instructions"])
        self.assertEqual("extruct", data["strategy"])
        self.assertTrue(data["schema_recipe"])
        self.assertIsInstance(data["quality_score"], int)
        self.assertNotIn("notes", data)
        self.assertNotIn("ingredients_parsed", data)

    def test_scrape_v2_timeout_returns_500(self):
        with patch(
            "mycookybook_api.app.requests.get",
            side_effect=requests.Timeout("delai depasse"),
        ):
            response = self.client.get("/scrape-v2", query_string={"webUrl": RECIPE_URL})
        body = response.get_json()

        self.assertEqual(500, response.status_code)
        self.assertFalse(body["success"])
        self.assertIn("delai depasse", body["message"])

    def test_parse_ingredient_contract(self):
        missing = self.client.post("/parse-ingredient", json={})
        self.assertEqual(400, missing.status_code)
        self.assertFalse(missing.get_json()["success"])
        self.assertEqual("Missing parameter: ingredient", missing.get_json()["message"])

        response = self.client.post(
            "/parse-ingredient",
            json={"ingredient": "200 g de farine", "language": "fr"},
        )
        body = response.get_json()
        data = body["data"]

        self.assertEqual(200, response.status_code)
        self.assertTrue(body["success"])
        self.assertEqual("Success", body["message"])
        self.assertEqual("200 g de farine", data["raw"])
        self.assertEqual("farine", data["ingredient"])
        self.assertEqual(200.0, data["quantity"])
        self.assertEqual("g", data["unit"])
        self.assertIn("note", data)
        self.assertEqual("fr", data["detected_language"])

    def test_parse_ingredients_contract(self):
        missing = self.client.post("/parse-ingredients", json={"ingredients": "pas une liste"})
        self.assertEqual(400, missing.status_code)
        self.assertIn("must be a list", missing.get_json()["message"])

        response = self.client.post(
            "/parse-ingredients",
            json={"ingredients": ["200 g de farine", "2 oeufs"], "language": "fr"},
        )
        body = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertTrue(body["success"])
        self.assertEqual(2, body["data"]["count"])
        self.assertEqual("farine", body["data"]["ingredients"][0]["ingredient"])
        self.assertEqual("g", body["data"]["ingredients"][0]["unit"])
        for item in body["data"]["ingredients"]:
            self.assertEqual(PARSED_INGREDIENT_KEYS, set(item))

    def test_parse_ingredient_exception_returns_500(self):
        with patch("mycookybook_api.app.ingredient_parser.parse", side_effect=RuntimeError("parser")):
            response = self.client.post(
                "/parse-ingredient",
                json={"ingredient": "200 g de farine", "language": "fr"},
            )
        body = response.get_json()

        self.assertEqual(500, response.status_code)
        self.assertFalse(body["success"])
        self.assertIn("parser", body["message"])
        self.assertEqual({}, body["data"])


if __name__ == "__main__":
    unittest.main()
