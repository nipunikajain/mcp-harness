"""
MCP server: "Order Assistant".

Exposes one tool, get_order_status, which fetches order data from the order API
over HTTP (see order_api.py — a simulated business API, not a real backend).

Run:  .venv/bin/mcp run server.py:mcp --transport streamable-http
"""

import os
from typing import Optional

import httpx2
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

mcp = MCPServer("Order Assistant")

# Where the order API lives, and how long we are willing to wait for it.
ORDER_API_BASE_URL = os.environ.get("ORDER_API_BASE_URL", "http://127.0.0.1:8001")
ORDER_API_TIMEOUT_SECONDS = float(os.environ.get("ORDER_API_TIMEOUT_SECONDS", "5.0"))


class OrderStatus(BaseModel):
    """Explicit result shape for get_order_status."""

    found: bool
    order_id: str
    status: Optional[str] = None
    estimated_delivery: Optional[str] = None
    message: Optional[str] = None


class OrderAPIUnavailable(ToolError):
    """The order API could not be reached, or did not answer usably.

    Raised — rather than returned — so the caller sees a failed tool call. A
    returned OrderStatus always means the API answered; this means it did not,
    and we genuinely do not know the order's status.

    Subclasses the SDK's ToolError (an *anticipated* failure) so our message
    reaches the agent. A plain Exception would be treated as a crash and the
    agent would see only "Error executing tool get_order_status".
    """


@mcp.tool()
async def get_order_status(order_id: str) -> OrderStatus:
    """Retrieve an order's current status and estimated delivery date."""
    url = f"{ORDER_API_BASE_URL}/orders/{order_id}"

    try:
        async with httpx2.AsyncClient(timeout=ORDER_API_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx2.TimeoutException as exc:
        raise OrderAPIUnavailable(f"Order API timed out after {ORDER_API_TIMEOUT_SECONDS}s: {url}") from exc
    except httpx2.RequestError as exc:
        raise OrderAPIUnavailable(f"Order API unreachable at {url}: {exc}") from exc

    # A 404 is the API answering "no such order" — a normal, known outcome.
    if response.status_code == 404:
        return OrderStatus(
            found=False,
            order_id=order_id,
            message="No order exists with this ID.",
        )

    # Anything other than 200 means we cannot vouch for the answer.
    if response.status_code != 200:
        raise OrderAPIUnavailable(
            f"Order API returned HTTP {response.status_code} for {url}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise OrderAPIUnavailable(f"Order API returned non-JSON body for {url}") from exc

    return OrderStatus(
        found=True,
        order_id=order_id,
        status=payload.get("status"),
        estimated_delivery=payload.get("estimated_delivery"),
    )
