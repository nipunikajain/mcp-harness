"""
SIMULATED BUSINESS API — NOT A REAL ORDER SYSTEM.

This is a stand-in for a real order-management service that would normally live
in another team's system. Every order below is fictional test data. Nothing here
talks to a real backend, database, or payment system.

It exists so the MCP server in server.py has a genuine HTTP dependency to call
across a network boundary, instead of an in-process dictionary.

Run:  .venv/bin/python order_api.py          (listens on :8001 by default)
"""

import os

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

# --- Fictional fixtures. Not real orders. -----------------------------------
ORDERS = {
    "1042": {"status": "shipped", "estimated_delivery": "2026-09-18"},
    "1043": {"status": "processing", "estimated_delivery": None},
}


async def get_order(request):
    """GET /orders/{order_id} -> 200 with the order, or 404 if unknown."""
    order_id = request.path_params["order_id"]
    order = ORDERS.get(order_id)

    if order is None:
        return JSONResponse(
            {"error": "not_found", "order_id": order_id},
            status_code=404,
        )

    return JSONResponse({"order_id": order_id, **order})


async def health(request):
    return JSONResponse({"ok": True, "simulated": True})


app = Starlette(
    routes=[
        Route("/orders/{order_id}", get_order, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
    ]
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("ORDER_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("ORDER_API_PORT", "8001")),
        log_level="warning",
    )
