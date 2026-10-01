"""
Manifest for the reference "orders" integration.

Describes the tool that already exists in server.py today. The handler module
it points at (integrations/orders/handlers.py) is created in Milestone 3, when
the tool moves out of server.py. Until then this manifest is validated as
data, not imported as code.

The order API it targets is SIMULATED with fictional fixtures (see
order_api.py). Nothing here touches a real order system.
"""

from harness.contract import (
    IntegrationManifest,
    SettingSpec,
    ToolBehavior,
    ToolSpec,
    UpstreamSpec,
    validate_manifest,
)

manifest: IntegrationManifest = validate_manifest(
    {
        "name": "orders",
        "version": "0.1.0",
        "description": "Look up the status of a customer order by its numeric ID.",
        "upstream": {
            "name": "the order system",
            "base_url_setting": "ORDERS_API_BASE_URL",
            "timeout_seconds": 5.0,
        },
        "required_settings": [
            {
                "name": "ORDERS_API_BASE_URL",
                "description": "Base URL of the order API, e.g. http://127.0.0.1:8001",
                "default": "http://127.0.0.1:8001",
            },
        ],
        "tools": [
            {
                "name": "get_order_status",
                "description": (
                    "Retrieve an order's current status and estimated delivery date. "
                    "Use when a user asks about a specific order by its numeric ID."
                ),
                "handler": "handlers:get_order_status",
                "behavior": {"read_only": True},
            },
        ],
    }
)
