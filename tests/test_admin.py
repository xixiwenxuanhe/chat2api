import unittest

from fastapi import HTTPException

from api.admin import _credential_record, _extract_tokens
from chatgpt.modelCatalog import to_openai_model_list


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
        self.assertEqual(result["data"][0]["context_length"], 137000)

if __name__ == "__main__":
    unittest.main()
