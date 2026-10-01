# Roadmap

We plan by completed outcomes, not dates. Each milestone ends with a
handover and an understanding check before the next starts (see
`CLAUDE.md` §3). Status: ⬜ not started · 🔄 in progress · ✅ accepted.

**Product:** an agent-assisted MCP server builder — a reusable **harness**,
**integrations** conforming to a shared contract, and a **builder** that turns
an API specification and a user task into a proposed, reviewed, generated and
tested integration. Orders is a reference integration and regression test,
not the product's domain.

| # | Milestone | Deliver | Completion evidence | Status |
|---|---|---|---|---|
| 1 | **Architecture & integration contract** | `docs/ARCHITECTURE.md`; `harness/contract.py`; reference manifests (orders + an unrelated example); supported-spec subset | Valid manifests pass; malformed manifests give actionable errors; contract describes both orders and an unrelated example | 🔄 |
| 2 | **Generic MCP harness** | `harness/config.py`, `loader.py`, `server.py`; thin root entrypoint; example config with precedence defaults < file < env | No enabled integrations → zero tools; unknown integration → clear startup failure; disabled → not imported; duplicate tool names / missing settings → clear failures; minimal test integration callable; `list_tools()` schemas correct, no internal deps leaking | ⬜ |
| 3 | **Orders into the contract; shared HTTP utilities** | `integrations/orders/{manifest,handlers}.py`; simulated API under the integration; shared HTTP/errors/logging; updated diagnostic client and checks | Existing/missing orders correct; invalid args rejected before any request; timeout, connection failure, malformed body, wrong-endpoint responses handled; `mcp run` works; a consumer agent demonstrably calls the tool via MCP | ⬜ |
| 4 | **Builder: analysis & proposal** | Spec + task + constraints → structured, versioned proposal (operations, tool names/descriptions, args, outputs, config needs, assumptions, unsupported features, spec references) | Relevant operation selected for a sample task; ambiguous task → clarification; unsupported feature flagged; proposal reviewable and editable before generation | ⬜ |
| 5 | **Builder: generation** | Manifest, typed handlers + output models, config example, integration checks, explanation — into staging, disabled by default | Generated files satisfy the contract; proposed signatures match implementation; generation never imports/enables/publishes | ⬜ |
| 6 | **Validate, repair, enable** | Isolated execution for generated code; fixture vs live checks; independent acceptance scenarios; bounded repair loop; review gate; re-review on change | Deliberately broken integration fails clearly; supported defect repaired and rechecked; unresolved defect stays disabled; approved integration usable by a consumer agent | ⬜ |
| 7 | **Prove it beyond orders** | Full journey on a second unrelated API: spec + task → review → generate → validate → approve → enable → connect → ask | No domain-specific harness changes; manual corrections documented; effort, attempts, check results and agent task results recorded, including failures | ⬜ |
| 8 | **Package the public release** | Reproducible install/startup; dependency manifest; `.gitignore`, safe config examples, licence, CONTRIBUTING/SECURITY; README; example specs and fictional fixtures; demo; test/eval instructions | Clean checkout follows the docs; another person attempts setup and friction is addressed; secret scan before publishing. Local end-to-end only — not production-ready | ⬜ |

Authenticated remote deployment is a later milestone, after release 1.

## Working method, every milestone

**Before:** purpose, proposed changes, acceptance criteria, main tradeoff.

**After:** a handover covering what was built, how execution flows (commands,
entrypoints, call order, network boundaries, error paths, a small diagram),
why these choices, evidence (commands run and observed results, marked
`[VERIFIED]` / `[INSPECTED]` / `[VERIFIED-USER]` / untested), limitations, a
hands-on exercise, and a 60–90 second interview explanation by the user.
`decisions.txt` and `EXECUTION_FLOW.md` are updated as part of the milestone.
Then a 3–5 question open-ended quiz, one question at a time, including at
least one "what would happen if…". No commit, push or next milestone without
explicit acceptance. Passing the quiz does not replace technical verification.
