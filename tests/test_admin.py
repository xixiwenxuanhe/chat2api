import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import utils.globals as globals
from api.admin import _credential_record
from chatgpt.credentials import parse_session_json, refresh_credential, upsert_credential
from chatgpt.modelCatalog import _model_parts, get_model_catalog, to_openai_model_list


class CredentialParsingTests(unittest.TestCase):
    def test_parses_complete_session_json(self):
        content = json.dumps({
            "accessToken": "eyJ-session-token",
            "sessionToken": "session-cookie",
            "account": {"id": "account-1"},
            "user": {"email": "member@example.com"},
        })
        credential = parse_session_json(content)
        self.assertEqual(credential["access_token"], "eyJ-session-token")
        self.assertEqual(credential["session_token"], "session-cookie")
        self.assertEqual(credential["account_id"], "account-1")
        self.assertEqual(credential["email"], "member@example.com")

    def test_rejects_incomplete_session_json(self):
        with self.assertRaises(HTTPException) as context:
            parse_session_json('{"accessToken":"eyJ-only"}')
        self.assertEqual(context.exception.status_code, 400)

    def test_credential_record_never_exposes_tokens(self):
        credential = parse_session_json(json.dumps({
            "accessToken": "eyJ-sensitive-access",
            "sessionToken": "sensitive-session",
            "account": {"id": "account-1"},
        }))
        record = _credential_record(credential)
        self.assertNotIn("eyJ-sensitive-access", record.values())
        self.assertNotIn("sensitive-session", record.values())


class CredentialStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_replaces_same_account(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials_file = os.path.join(directory, "credentials.json")
            original = list(globals.credential_list)
            credential_list = globals.credential_list
            credential_list.clear()
            try:
                with patch("chatgpt.credentials.globals.CREDENTIALS_FILE", credentials_file):
                    first, created = await upsert_credential(json.dumps({
                        "accessToken": "eyJ-first",
                        "sessionToken": "session-first",
                        "account": {"id": "account-1"},
                    }))
                    second, created_again = await upsert_credential(json.dumps({
                        "accessToken": "eyJ-second",
                        "sessionToken": "session-second",
                        "account": {"id": "account-1"},
                    }))
                self.assertTrue(created)
                self.assertFalse(created_again)
                self.assertEqual(first["id"], second["id"])
                self.assertEqual(len(credential_list), 1)
                self.assertEqual(credential_list[0]["access_token"], "eyJ-second")
                self.assertEqual(os.stat(credentials_file).st_mode & 0o777, 0o600)
            finally:
                credential_list[:] = original

    async def test_refresh_updates_access_and_rotated_session(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials_file = os.path.join(directory, "credentials.json")
            original = list(globals.credential_list)
            credential = parse_session_json(json.dumps({
                "accessToken": "eyJ-stale",
                "sessionToken": "session-original",
                "account": {"id": "account-1"},
            }))
            globals.credential_list[:] = [credential]

            class Cookies:
                def __init__(self, values=()):
                    self.jar = [SimpleNamespace(name=name, value=value) for name, value in values]

            class Response:
                status_code = 200

                def __init__(self, access_token, cookies=()):
                    self.cookies = Cookies(cookies)
                    self._access_token = access_token

                def json(self):
                    return {
                        "accessToken": self._access_token,
                        "account": {"id": "account-1"},
                        "user": {"email": "member@example.com"},
                    }

            client = SimpleNamespace(
                get=AsyncMock(side_effect=[
                    Response("eyJ-intermediate", [("__Secure-next-auth.session-token", "session-rotated")]),
                    Response("eyJ-fresh"),
                ]),
                close=AsyncMock(),
                session=SimpleNamespace(cookies=Cookies()),
            )
            try:
                with patch("chatgpt.credentials.globals.CREDENTIALS_FILE", credentials_file), patch(
                    "chatgpt.credentials.Client", return_value=client
                ):
                    refreshed = await refresh_credential(credential["id"])
                self.assertEqual(refreshed["access_token"], "eyJ-fresh")
                self.assertEqual(refreshed["session_token"], "session-rotated")
                self.assertEqual(refreshed["email"], "member@example.com")
                self.assertEqual(client.get.await_count, 2)
                self.assertIn("session-rotated", client.get.await_args_list[1].kwargs["headers"]["cookie"])
            finally:
                globals.credential_list[:] = original


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
