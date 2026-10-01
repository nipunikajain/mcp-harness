"""
Manifest for a FICTIONAL weather-lookup integration.

This is a contract exercise, not a working integration: there is no handler,
no upstream, and no real weather provider behind it. It exists so the
contract is tested against something that is not about orders -- a different
domain, a secret setting, and two tools instead of one.
"""

from harness.contract import IntegrationManifest, validate_manifest

manifest: IntegrationManifest = validate_manifest(
    {
        "name": "weather_lookup",
        "version": "0.0.1",
        "description": "Current conditions and short-range forecast for a named city (fictional example).",
        "upstream": {
            "name": "the weather service",
            "base_url_setting": "WEATHER_API_BASE_URL",
            "timeout_seconds": 3.0,
        },
        "required_settings": [
            {
                "name": "WEATHER_API_BASE_URL",
                "description": "Base URL of the weather provider.",
                "default": "https://weather.example",
            },
            {
                "name": "WEATHER_API_KEY",
                "description": "API key for the weather provider. Supplied via environment; never stored in files.",
                "secret": True,
            },
        ],
        "tools": [
            {
                "name": "get_current_conditions",
                "description": "Current temperature and conditions for a city. Use for 'what's the weather in X right now'.",
                "handler": "handlers:get_current_conditions",
                "behavior": {"read_only": True},
            },
            {
                "name": "get_forecast",
                "description": "Daily forecast for the next few days for a city.",
                "handler": "handlers:get_forecast",
                "behavior": {"read_only": True, "idempotent": False},
            },
        ],
    }
)
