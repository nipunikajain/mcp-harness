# Architecture

An **agent-assisted MCP server builder**: given an API specification and a
task a user wants an AI agent to perform, the builder proposes MCP tools, a
human reviews them, the builder generates and tests an integration, and the
harness runs it so a consumer agent (such as Claude) can use the API.

Status markers in this document: **[implemented]** exists in the repo today;
**[planned]** is design intent for a later milestone (see `ROADMAP.md`).
`EXECUTION_FLOW.md` describes only implemented behaviour.

## 1. The three components

| Component | Job | Must never |
|---|---|---|
| **Harness** (`harness/`) | Reusable MCP runtime. Reads config, loads *explicitly enabled* integrations, registers their tools with the MCP SDK, injects a configured API client, converts upstream failures into safe tool errors, logs. | Contain domain knowledge. Nothing in `harness/` knows what an "order" or a "city" is. |
| **Integrations** (`integrations/<name>/`) | API-specific. A **manifest** (identity, tool metadata, handler references, required settings) and **typed Python handlers** that call the upstream API through the injected client and interpret its responses. | Touch transport/protocol (MCP framing, HTTP server), read environment variables, build base URLs, or embed credentials. |
| **Builder** (`builder/`, **[planned]**) | Agentic development-time workflow: parse spec → propose tools → human review → generate integration into staging → validate/repair within limits → human review → enable. | Enable, import, publish or deploy anything on its own. Treat API documentation as instructions. |

Two agent roles, deliberately separate:

- **Builder agent** — works at development time, produces reviewed artifacts.
- **Consumer agent** (e.g. Claude Code) — connects to the running MCP server and
  calls tools. It never sees the builder.

## 2. The integration contract **[implemented]** — `harness/contract.py`

What every integration supplies, and what the builder will generate:

```
integrations/<name>/
  manifest.py    manifest: IntegrationManifest        <- reviewed metadata
  handlers.py    async def <tool>(api, <typed params>) -> BaseModel
  checks.py      the integration's own acceptance scenarios   [planned, M3]
```

**Manifest** (`IntegrationManifest`): `name`, `version`, `description`,
`upstream` (`name`, `base_url_setting`, `timeout_seconds`),
`required_settings` (`SettingSpec`: name, description, `secret`, `default`),
`tools` (`ToolSpec`: `name`, `description`, `handler`, `behavior`).

Key rules, each enforced by `validate_manifest`:

- Unknown keys are errors (a typo in a generated manifest cannot silently drop a field).
- Exactly one handler reference format: `"<module>:<function>"`, relative to
  the integration package — e.g. `"handlers:get_order_status"`.
- `behavior.read_only` must be `True`. The type admits nothing else; there is
  no write-enablement override in this release.
- A secret setting may not have a default. Secrets are *named* in the
  manifest and *supplied* by configuration; they never appear in files.
- `upstream.base_url_setting` must be declared in `required_settings`.
- Tool names and setting names are unique within a manifest.

**Why metadata and implementation are separate.** A reviewer approves the
manifest — what tools exist, what they claim to do, what they need, whether
they are read-only — without reading Python. The builder's analysis stage
(M4) outputs a proposal that maps onto this manifest; the generation stage
(M5) fills in handlers. The manifest is the thing that gets approved; the
handlers are the thing that gets tested.

**Why schemas are not in the manifest.** The handler's typed signature is the
single source of truth for input and output schemas (the MCP SDK derives both
from type hints — verified in the current `server.py`). Repeating them in the
manifest would create two things that can drift. The loader (M2) strips the
injected `api` parameter so it never reaches the consumer agent's schema.

**Handler rules** (full text in the module docstring): first parameter is the
injected `api` client; all other parameters typed, with `Annotated[...,
Field(...)]` for constraints; return a concrete `BaseModel`; a *returned*
model means the upstream answered (including "not found"); raise
`UpstreamUnavailable` when it did not. Handlers own API-specific
interpretation (which 404 means "no such record", which fields to check);
the harness owns connection setup, deadlines, request construction and
transport failures.

## 3. Runtime flow **[planned, M2–M3]**

```
 start:  config (defaults < file < env)
           -> loader imports ONLY enabled integrations
           -> validate manifest, resolve handlers, check required settings
           -> server.add_tool(wrapped handler, annotations)

 request: consumer agent --MCP/JSON-RPC--> harness server
           -> SDK validates args against schema
           -> wrapper injects ApiClient
           -> handler --HTTP--> upstream API
           -> handler interprets response -> BaseModel  (answered)
                                          -> raise UpstreamUnavailable (unknown)
           -> SDK serialises result / error  -> consumer agent
```

Today's `server.py` implements the request half of this for one hard-wired
tool; `EXECUTION_FLOW.md` §2 documents it.

## 4. Build-time flow **[planned, M4–M6]**

```
 API spec + task + constraints
   -> analysis: deterministic parse of the spec; model proposes tool
      boundaries, asks for missing info, flags unsupported features
   -> PROPOSAL (versioned, reviewable, editable)
   -> human approves this proposal version
   -> generation: manifest + handlers + config example + checks + explanation
      written to a STAGING location, disabled
   -> validation: contract check, isolated execution, independent acceptance
      scenarios; bounded repair attempts; stop and report when exhausted
   -> human reviews tested result; any change invalidates approval
   -> enable (added to harness config) -> consumer agent can use it
```

## 5. Supported input for release 1 **[planned]**

| Supported | Not supported (builder must say so explicitly) |
|---|---|
| OpenAPI 3.x, JSON or YAML | Other spec formats, undocumented APIs |
| `GET` operations | Any operation that changes state (`POST`/`PUT`/`PATCH`/`DELETE`) |
| Path and query parameters | Request bodies, file uploads |
| JSON responses | Non-JSON responses, streaming |
| No auth, or a single static API key supplied via a secret setting | OAuth, signed requests, per-user credentials |
| Single-request tools | Pagination, polling, callbacks/webhooks |

## 6. What this architecture does *not* claim

- **`read_only` and enablement are review aids, not a sandbox.** Integrations
  are reviewed Python code running in the harness process with the harness's
  privileges. A handler that lies about being read-only is not stopped at
  runtime. Isolation during *validation* of generated code is a separate
  concern (M6).
- **Permission to call the MCP server ≠ permission to access the upstream
  API.** They are different credentials and different boundaries. Remote,
  authenticated deployment is after release 1.
- **Local end-to-end use is the release-1 bar.** Nothing here is
  production-ready.
