"""
The harness: a reusable MCP runtime that loads explicitly enabled integrations.

Milestone 1 ships only the integration contract (`harness.contract`). The
runtime pieces (config, loader, server) arrive in Milestone 2. See
docs/ARCHITECTURE.md for the boundary between harness, integrations and builder.

Rule for this package: no domain knowledge. Nothing in here may know what an
"order" is.
"""
