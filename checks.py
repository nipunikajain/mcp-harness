"""
Focused integration checks for the MCP harness.

Self-contained: starts the simulated order API and the MCP server as
subprocesses on dedicated ports, exercises the four acceptance scenarios
through a real MCP client, then tears both down.

Run:  .venv/bin/python checks.py

Note on ports: these checks deliberately do NOT use 8000/8001. They bind their
own ports and REFUSE TO RUN if those ports are already occupied. An earlier
version trusted port 8000, silently connected to a stale server left running
from a previous session, and reported passes that never touched this code.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys

from mcp import Client

HERE = os.path.dirname(os.path.abspath(__file__))
PY_BIN = os.path.join(HERE, ".venv", "bin", "python")

API_PORT = int(os.environ.get("CHECKS_API_PORT", "8011"))
MCP_PORT = int(os.environ.get("CHECKS_MCP_PORT", "8010"))
MCP_URL = f"http://127.0.0.1:{MCP_PORT}/mcp"
API_BASE = f"http://127.0.0.1:{API_PORT}"

results = []


def record(name, passed, detail):
    results.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}\n       {detail}")


def port_is_free(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


async def wait_for_port(port, proc, timeout=25.0):
    """Wait until port accepts connections. Fail fast if the process died."""
    for _ in range(int(timeout / 0.25)):
        if proc.poll() is not None:
            return False
        if not port_is_free(port):
            return True
        await asyncio.sleep(0.25)
    return False


def payload_of(result):
    """Pull the tool's JSON out of whichever channel actually carries it.

    structured_content has been observed as None, with the JSON arriving in a
    text content block instead, so we check both rather than assuming either.
    """
    if result.structured_content:
        return result.structured_content, "structured_content"
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text), "text block"
            except ValueError:
                return {"_raw": text}, "text block (non-JSON)"
    return None, "nothing"


async def main():
    # Pre-flight: never run against something we did not start.
    for port in (API_PORT, MCP_PORT):
        if not port_is_free(port):
            print(f"ABORT: port {port} is already in use. Free it or set "
                  f"CHECKS_API_PORT / CHECKS_MCP_PORT. Refusing to run against "
                  f"a server these checks did not start.")
            return 1

    api_env = {**os.environ, "ORDER_API_PORT": str(API_PORT)}
    mcp_env = {**os.environ, "ORDER_API_BASE_URL": API_BASE}

    api = subprocess.Popen([PY_BIN, "order_api.py"], cwd=HERE, env=api_env)
    server = subprocess.Popen(
        [PY_BIN, "-c",
         f"import asyncio, server; "
         f"asyncio.run(server.mcp.run_streamable_http_async(port={MCP_PORT}))"],
        cwd=HERE, env=mcp_env,
    )

    try:
        if not await wait_for_port(API_PORT, api):
            print("order API never came up on", API_PORT)
            return 1
        if not await wait_for_port(MCP_PORT, server):
            print("MCP server never came up on", MCP_PORT)
            return 1

        async with Client(MCP_URL) as client:
            tools = await client.list_tools()
            names = [t.name for t in tools.tools]
            record("tool is discoverable", "get_order_status" in names, f"tools={names}")

            # --- 1042: shipped, with its fixture delivery date ---------------
            r = await client.call_tool("get_order_status", {"order_id": "1042"})
            data, channel = payload_of(r)
            ok = (
                not r.is_error
                and data
                and data.get("found") is True
                and data.get("status") == "shipped"
                and data.get("estimated_delivery") == "2026-09-18"
            )
            record("1042 -> shipped + delivery date", ok, f"via {channel}: {data}")

            # --- 1043: processing, no delivery date --------------------------
            r = await client.call_tool("get_order_status", {"order_id": "1043"})
            data, channel = payload_of(r)
            ok = (
                not r.is_error
                and data
                and data.get("found") is True
                and data.get("status") == "processing"
                and data.get("estimated_delivery") is None
            )
            record("1043 -> processing, no delivery date", ok, f"via {channel}: {data}")

            # --- 9999: clearly not found, and NOT an error -------------------
            r = await client.call_tool("get_order_status", {"order_id": "9999"})
            data, channel = payload_of(r)
            ok = not r.is_error and data and data.get("found") is False
            record("9999 -> not found (not an error)", ok, f"via {channel}: {data}")

            # --- API down: execution failure, NOT "order not found" ----------
            api.terminate()
            api.wait(timeout=10)
            failed_loudly = False
            detail = ""
            try:
                r = await client.call_tool("get_order_status", {"order_id": "1042"})
                data, channel = payload_of(r)
                # It must NOT masquerade as a clean not-found result.
                looks_like_not_found = bool(data) and data.get("found") is False
                blob = json.dumps(data) if data else ""
                explains_why = "unreachable" in blob or "timed out" in blob
                failed_loudly = (
                    bool(r.is_error) and not looks_like_not_found and explains_why
                )
                detail = f"is_error={r.is_error} via {channel}: {data}"
            except Exception as exc:
                failed_loudly = True
                detail = f"client raised {type(exc).__name__}: {exc}"
            record("API down -> execution failure, not not-found", failed_loudly, detail)

    finally:
        for proc in (api, server):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
