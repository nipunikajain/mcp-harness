# mcp-harness

An **agent-assisted MCP server builder** (in progress). Give it an API
specification and a task you want an AI agent to perform; a builder agent
proposes MCP tools, you review them, it generates and tests the integration,
and a reusable harness runs it so a consumer agent such as Claude can use your
API. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and
[`docs/ROADMAP.md`](docs/ROADMAP.md) for where we are.

**What runs today** is the reference integration the product is being
extracted from: an agent asks for an order's status; an MCP server answers by
calling a simulated order API over HTTP. The rest of this README describes
that.

```
agent / client  --MCP/HTTP-->  server.py  --HTTP-->  order_api.py
   (:8000/mcp, streamable-http)            (:8001, SIMULATED)
```

`order_api.py` is a **simulated business API** with fictional fixtures. It is a
stand-in for a real order system — it has no real backend.

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run it

Two processes, two terminals. **Start the order API first** — the MCP server
calls it on every request.

```bash
# terminal 1 — simulated order API on :8001
.venv/bin/python order_api.py

# terminal 2 — MCP server on :8000
.venv/bin/mcp run server.py:mcp --transport streamable-http
```

Then, in a third terminal, the diagnostic client:

```bash
.venv/bin/python client.py
```

## Integration checks

Self-contained — starts and stops both processes itself, on ports 8010/8011 so
it never collides with a server you have running:

```bash
.venv/bin/python checks.py
```

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `ORDER_API_BASE_URL` | `http://127.0.0.1:8001` | `server.py` |
| `ORDER_API_TIMEOUT_SECONDS` | `5.0` | `server.py` |
| `ORDER_API_HOST` / `ORDER_API_PORT` | `127.0.0.1` / `8001` | `order_api.py` |

`mcp run` has no port flag; it always binds 8000.

## Docs

- `EXECUTION_FLOW.md` — how a request actually travels through the system.
- `decisions.txt` — why things are built this way.
- `CLAUDE.md` — the workflow for changing this project.
