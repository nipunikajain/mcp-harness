"""
Contract tests. Run:  .venv/bin/python -m unittest discover tests

Two jobs: (1) both reference manifests validate, (2) each malformed manifest
produces an InvalidManifest whose message names the offending field, so the
error is actionable for a builder agent or a human.
"""

import copy
import unittest

from harness.contract import InvalidManifest, IntegrationManifest, validate_manifest

VALID = {
    "name": "sample",
    "version": "1.0.0",
    "description": "A sample integration.",
    "upstream": {"name": "the sample service", "base_url_setting": "SAMPLE_API_BASE_URL"},
    "required_settings": [
        {"name": "SAMPLE_API_BASE_URL", "description": "Base URL."},
    ],
    "tools": [
        {
            "name": "get_thing",
            "description": "Get a thing.",
            "handler": "handlers:get_thing",
            "behavior": {"read_only": True},
        },
    ],
}


def variant(**changes):
    """Deep-copy VALID and apply `path=value` changes, where path uses '.' and ints for lists."""
    data = copy.deepcopy(VALID)
    for path, value in changes.items():
        parts = path.split("__")
        target = data
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        last = parts[-1]
        if isinstance(target, list):
            target[int(last)] = value
        else:
            target[last] = value
    return data


class ReferenceManifests(unittest.TestCase):
    def test_orders_manifest_validates(self):
        from integrations.orders.manifest import manifest

        self.assertIsInstance(manifest, IntegrationManifest)
        self.assertEqual(manifest.name, "orders")
        self.assertEqual([t.name for t in manifest.tools], ["get_order_status"])
        self.assertTrue(all(t.behavior.read_only for t in manifest.tools))

    def test_unrelated_example_validates(self):
        from integrations.examples.weather_lookup.manifest import manifest

        self.assertEqual(manifest.name, "weather_lookup")
        self.assertEqual(len(manifest.tools), 2)
        secrets = [s.name for s in manifest.required_settings if s.secret]
        self.assertEqual(secrets, ["WEATHER_API_KEY"])


class MalformedManifests(unittest.TestCase):
    def assertRejected(self, data, *must_mention):
        with self.assertRaises(InvalidManifest) as ctx:
            validate_manifest(data)
        message = str(ctx.exception)
        for fragment in must_mention:
            self.assertIn(fragment, message, f"error message should mention {fragment!r}:\n{message}")
        return message

    def test_valid_baseline(self):
        validate_manifest(VALID)

    def test_bad_integration_slug(self):
        self.assertRejected(variant(name="Orders-API"), "name")

    def test_duplicate_tool_names(self):
        data = copy.deepcopy(VALID)
        data["tools"].append(copy.deepcopy(data["tools"][0]))
        self.assertRejected(data, "duplicate tool names", "get_thing")

    def test_handler_ref_dotted_not_colon(self):
        self.assertRejected(variant(tools__0__handler="handlers.get_thing"), "tools.0.handler", "<module>:<function>")

    def test_handler_ref_bare_function(self):
        self.assertRejected(variant(tools__0__handler="get_thing"), "tools.0.handler")

    def test_read_only_false_is_rejected(self):
        self.assertRejected(variant(tools__0__behavior={"read_only": False}), "tools.0.behavior.read_only")

    def test_read_only_missing_is_rejected(self):
        self.assertRejected(variant(tools__0__behavior={}), "tools.0.behavior.read_only")

    def test_secret_with_default(self):
        data = variant()
        data["required_settings"][0].update(secret=True, default="not-a-real-key")
        self.assertRejected(data, "required_settings.0", "secret")

    def test_base_url_setting_not_declared(self):
        self.assertRejected(variant(upstream__base_url_setting="OTHER_URL"), "OTHER_URL", "required_settings")

    def test_empty_tools(self):
        self.assertRejected(variant(tools=[]), "tools")

    def test_unknown_key_is_rejected(self):
        self.assertRejected(variant(tools__0__descripton="typo"), "descripton")

    def test_multiple_problems_reported_together(self):
        message = self.assertRejected(variant(name="Bad", tools__0__handler="nope"), "name", "tools.0.handler")
        self.assertGreaterEqual(message.count("\n"), 2)


if __name__ == "__main__":
    unittest.main()
