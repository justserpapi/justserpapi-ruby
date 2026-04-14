import copy
import os
import unittest
from unittest import mock

from scripts import sdkctl


MANIFEST = {
    "service": {
        "default_server_url": "https://api.justserpapi.com",
    }
}


class NormalizeSpecTest(unittest.TestCase):
    def sample_document(self):
        return {
            "openapi": "3.1.0",
            "info": {"title": "Example", "version": "1.0.0"},
            "servers": [{"url": "http://internal"}],
            "paths": {
                "/api/v1/google/search": {
                    "get": {
                        "tags": ["Google API"],
                        "operationId": "search",
                        "parameters": [
                            {
                                "name": "query",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "default": {
                                "description": "default response",
                                "content": {
                                    "application/json": {
                                        "examples": {
                                            "Example search response": {
                                                "value": {"code": 200, "data": {"answer": 42}}
                                            }
                                        }
                                    }
                                },
                            },
                            "401": {"description": "Authentication failed"},
                        },
                    }
                }
            },
        }

    def test_normalize_spec_injects_security_and_server(self):
        normalized = sdkctl.normalize_spec(self.sample_document(), MANIFEST)

        self.assertEqual("3.0.3", normalized["openapi"])
        self.assertEqual("https://api.justserpapi.com", normalized["servers"][0]["url"])
        self.assertIn("ApiKeyAuth", normalized["components"]["securitySchemes"])
        self.assertIn("ApiKeyQuery", normalized["components"]["securitySchemes"])
        self.assertEqual([{"ApiKeyAuth": [], "ApiKeyQuery": []}], normalized["security"])

    def test_normalize_spec_injects_generic_success_schema_and_preserves_examples(self):
        normalized = sdkctl.normalize_spec(self.sample_document(), MANIFEST)
        operation = normalized["paths"]["/api/v1/google/search"]["get"]

        self.assertEqual(["Google"], operation["tags"])
        self.assertEqual(
            {"$ref": "#/components/schemas/JustSerpApiResponse"},
            operation["responses"]["200"]["content"]["application/json"]["schema"],
        )
        self.assertIn(
            "Example search response",
            operation["responses"]["200"]["content"]["application/json"]["examples"],
        )
        self.assertEqual(
            sdkctl.UNEXPECTED_RESPONSE_DESCRIPTION,
            operation["responses"]["default"]["description"],
        )


class BreakingChangeDetectionTest(unittest.TestCase):
    def base_spec(self):
        spec = {
            "paths": {
                "/a": {
                    "get": {
                        "operationId": "a",
                        "parameters": [
                            {"name": "query", "in": "query", "required": True},
                            {"name": "page", "in": "query", "required": False},
                        ],
                    }
                }
            }
        }
        return spec

    def test_detect_breaking_changes_reports_removed_operation(self):
        baseline = self.base_spec()
        current = {"paths": {}}
        report = sdkctl.detect_breaking_changes(baseline, current)
        self.assertEqual(["GET /a"], report.removed_operations)

    def test_detect_breaking_changes_reports_newly_required_param(self):
        baseline = self.base_spec()
        current = copy.deepcopy(baseline)
        current["paths"]["/a"]["get"]["parameters"].append(
            {"name": "country", "in": "query", "required": True}
        )
        report = sdkctl.detect_breaking_changes(baseline, current)
        self.assertEqual(
            ["GET /a added required query param country"],
            report.newly_required_params,
        )


class FetchAuthResolutionTest(unittest.TestCase):
    def test_resolve_fetch_headers_supports_basic_auth(self):
        with mock.patch.dict(
            os.environ,
            {
                "JUSTSERPAPI_OPENAPI_USERNAME": "demo-user",
                "JUSTSERPAPI_OPENAPI_PASSWORD": "demo-pass",
            },
            clear=False,
        ):
            headers = sdkctl.resolve_fetch_headers()

        self.assertEqual("Basic ZGVtby11c2VyOmRlbW8tcGFzcw==", headers["Authorization"])

    def test_resolve_fetch_headers_omits_authorization_without_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            headers = sdkctl.resolve_fetch_headers()

        self.assertNotIn("Authorization", headers)


if __name__ == "__main__":
    unittest.main()
