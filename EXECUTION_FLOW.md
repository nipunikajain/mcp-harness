# EXECUTION_FLOW.md

How `mcp-harness` actually executes. Maintained per CLAUDE.md §2.

**Marker convention**
- `[VERIFIED]` — observed by actually running it.
- `[VERIFIED-USER]` — reported by the user as observed; not re-run by me.
- `[INSPECTED]` — concluded from reading code or package metadata; **not** run.

Never upgrade `[INSPECTED]` to `[VERIFIED]` without actually running it.

Last aligned with code: **2026-09-30**, after the HTTP-backed rewrite.

---

## 0. Environment

- Python **3.11.0**, venv at `.venv/`. `[VERIFIED]` — `.venv/pyvenv.cfg`.
- MCP SDK **`mcp` 2.2.0**. `[VERIFIED]` — `mcp-2.2.0.dist-info/METADATA`.
  `mcp.__version__` is not exposed, so dist-info is authoritative.
- Direct deps now declared in `requirements.txt`: `mcp`, `httpx2`, `starlette`,
  `uvicorn`, `pydantic`. All were already present as transitive deps of `mcp`;
  nothing new was installed. `[VERIFIED]`
- Not a git repository. `[VERIFIED]`

---

## 1. Components and startup

Three processes now, not one.

### A. Simulated order API — `order_api.py`

| | |
|---|---|
| Startup | `.venv/bin/python order_api.py` |
| Entry point | `order_api.py:__main__` → `uvicorn.run(app, ...)` |
| Listens | `127.0.0.1:8001` (`ORDER_API_HOST` / `ORDER_API_PORT`) |

Starlette app with two routes (`order_api.py:app`): `GET /orders/{order_id}` →
`order_api.py:get_order`, and `GET /health`. Fixtures live in
`order_api.py:ORDERS` — **fictional, clearly labelled simulated**. `[VERIFIED]`

### B. MCP server — `server.py`

| | |
|---|---|
| Startup | `.venv/bin/mcp run server.py:mcp --transport streamable-http` |
| Entry point | the `mcp` CLI imports the module and runs the `mcp` object |
| Listens | `127.0.0.1:8000/mcp` |

`server.py` still has **no `__main__` block** — that is by design; the `mcp` CLI
owns the entry point via the `file:object` spec. `[VERIFIED-USER]` that this
command serves successfully. `[VERIFIED]` that `mcp run --help` accepts exactly
this form and exposes **no port flag** — it always binds 8000.

`checks.py` instead calls `server.mcp.run_streamable_http_async(port=...)`
directly, because it needs a non-default port. Same server object, same
transport, different entry point. `[VERIFIED]`

### C. Diagnostic client — `client.py`

| | |
|---|---|
| Startup | `.venv/bin/python client.py` |
| Entry point | `client.py:__main__` → `asyncio.run(main())` |

Unchanged this milestone. Targets `http://localhost:8000/mcp`.

---

## 2. Representative request — "what is the status of order 1042?"

```
 agent / client.py          server.py                order_api.py     ORDERS
   (process A)              (process B)              (process C)     (in C)
        |                        |                        |             |
        |== MCP / JSON-RPC ====> |                        |             |
        |   streamable-http      |                        |             |
        |   127.0.0.1:8000/mcp   |                        |             |
        |                        |                        |             |
        | call_tool(             |  SDK validates args    |             |
        |  "get_order_status",   |  against input schema  |             |
        |  {"order_id":"1042"})  |         |              |             |
        |                        |  get_order_status()    |             |
        |                        |         |              |             |
        |                        |== HTTP GET ==========> |             |
        |                        |  /orders/1042          |  get_order  |
        |                        |  127.0.0.1:8001        |      |----->|
        |                        |                        |      |<-----|
        |                        | <===== 200 + JSON =====|             |
        |                        |   (or 404 if unknown)  |             |
        |                        |         |              |             |
        |                        |  build OrderStatus     |             |
        |                        |         |              |             |
        | <-- CallToolResult ----|  SDK serializes model  |             |
        |     .structured_content|                        |             |
        |     .content[]         |                        |             |
```

### Call order, with real names `[VERIFIED]` unless noted

1. `client.py:__main__` → `asyncio.run(main())`.
2. `Client("http://localhost:8000/mcp")` — transport open + MCP initialize
   handshake (SDK-managed).
3. `client.list_tools()` → `get_order_status` descriptor.
4. `client.call_tool("get_order_status", {"order_id": "1042"})`.
5. SDK validates arguments, dispatches to `server.py:get_order_status`.
6. `get_order_status` builds `f"{ORDER_API_BASE_URL}/orders/{order_id}"` and
   `await client.get(url)` via `httpx2.AsyncClient(timeout=...)`.
7. `order_api.py:get_order` reads `request.path_params["order_id"]`, does
   `ORDERS.get(order_id)`, returns `JSONResponse` 200 or 404.
8. Back in `get_order_status`: 404 → `OrderStatus(found=False, message=...)`;
   200 → `OrderStatus(found=True, status=..., estimated_delivery=...)`;
   anything else → `raise OrderAPIUnavailable`.
9. SDK serializes the `OrderStatus` model into the tool result.

---

## 3. Boundaries

**Two** process/network boundaries now, where there was one:

| Hop | Protocol | Address |
|---|---|---|
| agent/client → MCP server | MCP over JSON-RPC, streamable-http | `127.0.0.1:8000/mcp` |
| MCP server → order API | plain HTTP/JSON | `127.0.0.1:8001` |

The second hop is new and is the point of this milestone. `ORDERS` is now inside
`order_api.py`'s process, not the MCP server's — the MCP server holds no order
data at all. `[VERIFIED]`

---

## 4. Our code vs. the SDK

| Handled by **our code** | Handled by the **SDK** |
|---|---|
| The HTTP call and its URL construction | MCP transport, JSON-RPC framing, handshake |
| Timeout value and base URL config | Input-schema generation from type hints |
| 404 → `found=False` (a normal answer) | Argument validation |
| Non-200/timeout/non-JSON → raise | Dispatch to the handler |
| The `OrderStatus` shape | Output schema from the pydantic return model |
| Choosing `ToolError` over `Exception` | Serializing the model into the result |
| | Setting `is_error`; deciding whether our message reaches the agent |

---

## 5. Error paths

| Situation | Result | Status |
|---|---|---|
| Unknown order (API returns 404) | `found=False`, `is_error=False`, message "No order exists with this ID." | `[VERIFIED]` — order 9999 |
| API process down | `is_error=True`, text: `Error executing tool get_order_status: Order API unreachable at http://…/orders/1042: All connection attempts failed` | `[VERIFIED]` |
| API slow past the timeout | `OrderAPIUnavailable` via `httpx2.TimeoutException` | `[INSPECTED]` — **never exercised** |
| API returns 5xx / other non-200 | `OrderAPIUnavailable` | `[INSPECTED]` — **never exercised** |
| API returns non-JSON body | `OrderAPIUnavailable` | `[INSPECTED]` — **never exercised** |
| Bad/missing `order_id` argument | rejected by SDK schema validation before our code runs | `[INSPECTED]` |

**Why `OrderAPIUnavailable` subclasses `ToolError`.** The SDK treats `ToolError`
as an *anticipated* failure and passes our message through to the agent; any
other exception is treated as a crash and the agent sees only
`Error executing tool get_order_status`, with the real text kept server-side.
Both behaviours observed directly — the first implementation used a plain
`Exception` and produced exactly the generic message. `[VERIFIED]`

---

## 6. A correction to an earlier observation

Previously observed (with the old `-> dict` handler): `structured_content=None`,
JSON only in a text content block.

**That is no longer what happens.** With `-> OrderStatus` (a pydantic model), the
SDK derives an output schema and **`structured_content` is populated**:

```
via structured_content: {'found': True, 'order_id': '1042', 'status': 'shipped',
                         'estimated_delivery': '2026-09-18', 'message': None}
```

`[VERIFIED]` — all three success scenarios. The return annotation is what
changed the behaviour, not the SDK version.

`checks.py:payload_of` still reads **both** channels, preferring
`structured_content` and falling back to a text block, so it does not depend on
either. Error results still arrive as a **plain-text** block, not JSON —
`payload_of` reports those as `text block (non-JSON)`. `[VERIFIED]`

---

## 7. Known gaps

- **`client.py` has not been run against the new server.** Port 8000 is held by
  a stale MCP server from 09:27 running the *old* dict code; it is the user's
  process and was left alone.
- The timeout, non-200, and non-JSON branches are implemented but unexercised.
- `mcp run` as an entry point is `[VERIFIED-USER]`, not re-verified by me;
  `checks.py` covers `run_streamable_http_async` instead.
- ~~No natural-language agent test yet.~~ **Closed 2026-09-30 by the user:**
  `claude mcp add -t http order-assistant http://127.0.0.1:8000/mcp` connected,
  and with the API stopped the agent reported that it could not get the status
  and named the MCP-server/order-API split. `[VERIFIED-USER]`
- **Open issue (not yet addressed):** the `OrderAPIUnavailable` message embeds
  internal topology (the order-API URL, and the fact that the MCP server is up
  but its upstream is not). The agent relays that to the end user. Useful for a
  developer, too much for a customer, who only needs "can't fetch the status
  right now". Deciding where to draw that line is a separate change.

---

## Change log

### 2026-09-30 — Baseline (documentation only)

- **What changed in the execution flow:** nothing. `server.py` and `client.py`
  are untouched. This is the initial capture of the current state.
- **Why:** establish a baseline before any code changes, per CLAUDE.md §2.
- **How verified:** SDK version and Python version read from `dist-info`
  metadata and `pyvenv.cfg`; `MCPServer`/`Client` API surface confirmed by
  runtime introspection of the installed package. Source read in full.
- **What remains untested:** everything runtime. The server has no entry point,
  so no request has ever been served or observed. All of §2, §3, §5 is
  `[INSPECTED]` only.

### 2026-09-30 — `client.py` gained an output-schema print (change not made by me)

- **What changed in the execution flow:** `client.py:25` now prints
  `tool.output_schema` after `structured_content`. Read-only addition — it adds
  no MCP call and no new boundary; it inspects the already-fetched tool
  descriptor from step 3.
- **Why:** unknown — the edit arrived from outside this session (`client.py`
  changed from 830 bytes/Sep 18 to 904 bytes/Sep 30 09:29 mid-session).
  Apparent intent: check whether the SDK derives an output schema from the
  `-> dict` return annotation on `server.py:get_order_status`.
- **How verified:** not verified. Source re-read only; still nothing to connect
  to on port 8000.
- **What remains untested:** the new line itself, and the latent loop-variable
  issue noted in §2 — both would surface only on an actual run.

### 2026-09-30 — HTTP-backed order lookup (major change)

- **What changed in the execution flow:** a second network hop. `ORDERS` moved
  out of `server.py` into `order_api.py` on :8001;
  `server.py:get_order_status` became async and now does an HTTP GET instead of
  a dict lookup. Failure to reach the API raises instead of returning, so it
  surfaces as `is_error=True` rather than a false "not found".
- **Why:** the milestone requires a real business-API boundary, and the dict
  version could not distinguish "no such order" from "system unavailable".
- **How verified:** `checks.py` — 5/5, covering tool discovery plus all four
  acceptance scenarios (1042, 1043, 9999, API stopped), on isolated ports.
- **What remains untested:** timeout, non-200, and non-JSON branches;
  `client.py` against the new server; `mcp run` re-verification; any
  natural-language agent flow.

### 2026-09-30 — Correction: first checks run was a false pass

- **What changed:** nothing in the flow; a testing defect. The first `checks.py`
  run reported 4/5 while actually talking to a **stale server on :8000 running
  the old dict code**. Its own server had failed to bind, and the readiness
  probe could not tell the difference.
- **Why it changed:** `checks.py` now uses :8010/:8011, aborts if either port is
  occupied, and fails fast if a subprocess dies during startup.
- **How verified:** re-run after the fix — 5/5, with scenario 4 now genuinely
  failing loudly when the API is stopped.
- **What remains untested:** the guard itself has not been tested against a
  deliberately occupied 8010/8011.

### 2026-09-30 — Milestone 1: integration contract (no runtime change)

- **What changed in the execution flow:** nothing. `server.py`,
  `order_api.py`, `checks.py` and `client.py` are untouched; the request path
  in §2 is still exactly what runs. New code is data models and validation
  only: `harness/contract.py` (`IntegrationManifest`, `ToolSpec`,
  `validate_manifest`), two manifests under `integrations/`, and
  `tests/test_contract.py`. Nothing imports the MCP SDK or opens a socket.
- **Why:** the project was reframed as an agent-assisted MCP server builder
  (see `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`). The contract defines what
  the harness will load (Milestone 2) and what the builder will generate
  (Milestones 4–5) before either exists.
- **How verified:** `.venv/bin/python -m unittest discover tests` — 14/14
  `[VERIFIED]`; `.venv/bin/python checks.py` — still 5/5 `[VERIFIED]`;
  printed `integrations.orders.manifest.manifest` and a deliberately broken
  manifest's error text by hand `[VERIFIED]`.
- **What remains untested:** everything the contract *describes* about
  handlers (injection, schema stripping, `UpstreamUnavailable`) is
  **[planned]**, not implemented — `ARCHITECTURE.md` §3–4 carries the planned
  flows so this file never has to. The orders manifest references
  `handlers:get_order_status`, which does not exist yet.
