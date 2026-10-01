"""
The integration contract.

This module defines what every integration must supply so that:

  * the harness (Milestone 2) can load it without knowing its domain,
  * the builder (Milestones 4-5) knows exactly what to generate, and
  * a human reviewer can approve the *metadata* before reading any code.

It contains data models and validation only. There is deliberately no
runtime behaviour here: nothing imports handlers, opens connections, or
talks to the MCP SDK.

An integration is a Python package under `integrations/<name>/` containing:

    manifest.py   -> exposes `manifest: IntegrationManifest`   (described here)
    handlers.py   -> the async functions the manifest's tools point at
    checks.py     -> the integration's own acceptance scenarios (Milestone 3)

------------------------------------------------------------------------------
Handler requirements (documented here, enforced by the loader in Milestone 2)
------------------------------------------------------------------------------

    async def get_order_status(
        api: ApiClient,                                   # injected, see below
        order_id: Annotated[str, Field(pattern=r"^[0-9]+$", description="...")],
    ) -> OrderStatus:                                     # a concrete BaseModel
        ...

  1. The first parameter is `api`, an `ApiClient` configured from the
     manifest's `upstream` settings. The harness injects it; it is stripped
     from the tool's input schema and is never visible to the consumer agent.
  2. Every other parameter is typed. Use `Annotated[..., Field(...)]` for
     constraints and descriptions. The signature IS the input schema -- the
     manifest does not repeat it, so the two cannot drift apart.
  3. The return annotation is a concrete pydantic `BaseModel`. It IS the
     output schema. A *returned* model means "the upstream API answered",
     even when the answer is "not found".
  4. When the upstream API did not answer usably (unreachable, timed out,
     unexpected status, malformed body), the handler raises
     `UpstreamUnavailable` instead of returning. That reaches the agent as a
     failed tool call with a safe, generic message; diagnostic detail goes to
     the harness log.
  5. Handlers never read environment variables, build base URLs, or set
     timeouts themselves -- that is what `api` is for. Handlers DO own the
     interpretation of API-specific status codes and response bodies (which
     404 means "no such record", which fields to validate, and so on).

`ApiClient` and `UpstreamUnavailable` are Milestone 3 code and are referenced
by name only.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

# Identifier rules. Shared by integration names and tool names so that both
# are safe as Python identifiers, env-var fragments, and MCP tool names.
SLUG_PATTERN = r"^[a-z][a-z0-9_]*$"
SETTING_NAME_PATTERN = r"^[A-Z][A-Z0-9_]*$"

# Exactly one handler-reference format: "<module within the integration package>:<function>".
# e.g. "handlers:get_order_status" -> integrations/<name>/handlers.py::get_order_status
HANDLER_REF_PATTERN = r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*:[a-z_][a-z0-9_]*$"
_HANDLER_REF = re.compile(HANDLER_REF_PATTERN)


class _Strict(BaseModel):
    """Base for every contract model: unknown keys are errors, not ignored.

    A typo in a generated manifest ("descripton") must fail validation rather
    than silently produce a tool with no description.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SettingSpec(_Strict):
    """One configuration value the integration needs at runtime.

    Settings are *named* here and *supplied* by the harness config (env var
    of the same name, or a config file). Values -- especially secrets -- are
    never written into an integration's files.
    """

    name: str = Field(pattern=SETTING_NAME_PATTERN, description="Env-var style name, e.g. ORDERS_API_BASE_URL")
    description: str = Field(min_length=1)
    secret: bool = Field(default=False, description="True for API keys/tokens. Never logged, never defaulted.")
    default: Optional[str] = Field(default=None, description="Used when the setting is not supplied. Forbidden for secrets.")

    @model_validator(mode="after")
    def _secrets_have_no_default(self) -> "SettingSpec":
        if self.secret and self.default is not None:
            raise ValueError(f"setting {self.name!r} is marked secret and must not have a default")
        return self


class UpstreamSpec(_Strict):
    """The API this integration talks to."""

    name: str = Field(min_length=1, description="Human label, used in safe error text: '<name> is temporarily unavailable'.")
    base_url_setting: str = Field(
        pattern=SETTING_NAME_PATTERN,
        description="Name of the setting (declared in required_settings) that holds the base URL.",
    )
    timeout_seconds: float = Field(default=5.0, gt=0, le=120)


class ToolBehavior(_Strict):
    """Behavioural annotations, mirrored onto MCP ToolAnnotations by the loader.

    For this release every tool must declare `read_only=True`. The type admits
    nothing else, so there is no override to enable writes -- that is a
    deliberate product constraint, not a missing feature. Note that this is a
    *declaration* reviewed by a human; it is not enforced at runtime and is
    not a sandbox.
    """

    read_only: Literal[True] = Field(description="Must be True in this release. The tool must not change upstream state.")
    idempotent: bool = Field(default=True)
    open_world: bool = Field(default=True, description="True if the tool reaches outside the harness (it calls an upstream API).")


class ToolSpec(_Strict):
    """One MCP tool: its identity, its description, and where its code lives.

    Input and output schemas are NOT declared here. They come from the typed
    handler signature (see module docstring) so there is a single source of
    truth.
    """

    name: str = Field(pattern=SLUG_PATTERN, description="MCP tool name the consumer agent sees, e.g. get_order_status")
    description: str = Field(min_length=1, description="What the tool does and when to use it. The agent reads this.")
    handler: str = Field(description="'<module>:<function>' relative to the integration package, e.g. 'handlers:get_order_status'")
    behavior: ToolBehavior

    @field_validator("handler")
    @classmethod
    def _handler_ref_format(cls, value: str) -> str:
        if not _HANDLER_REF.match(value):
            raise ValueError(
                f"handler {value!r} must be '<module>:<function>' relative to the integration "
                f"package, e.g. 'handlers:get_order_status'"
            )
        return value


class IntegrationManifest(_Strict):
    """Everything the harness needs to know about an integration before importing its code."""

    name: str = Field(pattern=SLUG_PATTERN, description="Package name under integrations/, e.g. 'orders'")
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    upstream: UpstreamSpec
    required_settings: list[SettingSpec]
    tools: list[ToolSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _cross_field_rules(self) -> "IntegrationManifest":
        tool_names = [t.name for t in self.tools]
        dupes = sorted({n for n in tool_names if tool_names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate tool names: {', '.join(dupes)}")

        setting_names = [s.name for s in self.required_settings]
        dupes = sorted({n for n in setting_names if setting_names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate setting names: {', '.join(dupes)}")

        if self.upstream.base_url_setting not in setting_names:
            raise ValueError(
                f"upstream.base_url_setting {self.upstream.base_url_setting!r} is not declared in required_settings"
            )
        return self


class InvalidManifest(ValueError):
    """A manifest failed validation. The message lists one problem per line."""


def validate_manifest(data: Any) -> IntegrationManifest:
    """Validate a dict (or an existing model) into an IntegrationManifest.

    Pydantic's errors are re-shaped into one actionable line per problem,
    each naming the field path, so a builder or a human can act on them
    without reading a traceback.
    """
    try:
        return IntegrationManifest.model_validate(data)
    except ValidationError as exc:
        lines = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<manifest>"
            msg = err["msg"]
            # pydantic prefixes our ValueError text with "Value error, "; drop it.
            msg = msg.removeprefix("Value error, ")
            lines.append(f"{loc}: {msg}")
        raise InvalidManifest("invalid manifest:\n  " + "\n  ".join(lines)) from None
