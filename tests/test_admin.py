import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api.admin import _credential_record, _extract_tokens
from chatgpt.modelCatalog import _model_parts, get_model_catalog, to_openai_model_list


class CredentialParsingTests(unittest.TestCase):
    def test_extracts_access_token_from_session_json(self):
        content = '{"accessToken":"eyJ-session-token","sessionToken":"private"}'
        self.assertEqual(_extract_tokens(content), ["eyJ-session-token"])

    def test_extracts_unique_lines_without_comments(self):
        content = "# comment\neyJ-first\n\nrefresh-token"
        self.assertEqual(_extract_tokens(content), ["eyJ-first", "refresh-token"])

    def test_rejects_json_without_access_token(self):
        with self.assertRaises(HTTPException) as context:
            _extract_tokens('{"sessionToken":"private"}')
        self.assertEqual(context.exception.status_code, 400)

    def test_credential_record_never_exposes_full_token(self):
        token = "eyJ-this-is-a-sensitive-access-token-value"
        record = _credential_record(token)
        self.assertNotIn(token, record.values())
        self.assertEqual(record["type"], "access_token")


class ModelCatalogTests(unittest.TestCase):
    def test_uses_official_slug_as_openai_model_id(self):
        catalog = {"models": [{"slug": "gpt-5-6", "title": "GPT-5.6 Sol", "max_tokens": 137000}]}
        result = to_openai_model_list(catalog)
        self.assertEqual(result["data"][0]["id"], "gpt-5-6")
        self.assertEqual(result["data"][0]["max_tokens"], 137000)
        self.assertEqual(result["data"][0]["context_length"], 137000)

    def test_sorts_versions_variants_and_complex_suffix_groups(self):
        catalog = {"models": [
            {"slug": "gpt-5-5", "title": "GPT-5.5"},
            {"slug": "gpt-5.5-wm", "title": "GPT-5.5 WM"},
            {"slug": "gpt-5-6", "title": "GPT-5.6"},
            {"slug": "gpt-5-6-thinking", "title": "GPT-5.6 Thinking"},
            {"slug": "gpt-5-6-pro", "title": "GPT-5.6 Pro"},
            {"slug": "gpt-5-6-mini", "title": "GPT-5.6 Mini"},
            {"slug": "gpt-5-6-t-mini", "title": "GPT-5.6 Thinking Mini"},
            {"slug": "gpt-5.6-terra-wm", "title": "GPT-5.6 Terra"},
            {"slug": "gpt-5.6-sol-wm", "title": "GPT-5.6 Sol"},
            {"slug": "gpt-5-3-mini", "title": "GPT-5.3 Mini"},
        ]}
        result = to_openai_model_list(catalog)
        self.assertEqual(
            [model["id"] for model in result["data"]],
            [
                "gpt-5-6",
                "gpt-5-6-thinking",
                "gpt-5-6-mini",
                "gpt-5-6-pro",
                "gpt-5-5",
                "gpt-5.5-wm",
                "gpt-5-3-mini",
                "gpt-5-6-t-mini",
                "gpt-5.6-sol-wm",
                "gpt-5.6-terra-wm",
            ],
        )

    def test_parses_dot_dash_and_future_major_versions(self):
        self.assertEqual(_model_parts("gpt-5-6"), ((5, 6), []))
        self.assertEqual(_model_parts("gpt-5.6"), ((5, 6), []))
        self.assertEqual(_model_parts("gpt-6"), ((6, 0), []))
        self.assertEqual(_model_parts("gpt-6-thinking"), ((6, 0), ["thinking"]))


class ModelCatalogCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_cache_until_explicit_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_file = os.path.join(directory, "model_catalog.json")
            with open(cache_file, "w", encoding="utf-8") as file:
                json.dump({"updated_at": 100, "catalog": {"models": [{"slug": "cached"}]}}, file)

            upstream = AsyncMock(return_value={"models": [{"slug": "fresh"}]})
            with patch("chatgpt.modelCatalog.globals.MODEL_CATALOG_FILE", cache_file), patch(
                "chatgpt.modelCatalog._fetch_model_catalog", upstream
            ):
                catalog, updated_at = await get_model_catalog("token")
                self.assertEqual(catalog["models"][0]["slug"], "cached")
                self.assertEqual(updated_at, 100)
                upstream.assert_not_awaited()

                catalog, updated_at = await get_model_catalog("token", refresh=True)
                self.assertEqual(catalog["models"][0]["slug"], "fresh")
                self.assertGreater(updated_at, 100)
                upstream.assert_awaited_once_with("token")

if __name__ == "__main__":
    unittest.main()
