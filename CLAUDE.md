# CLAUDE.md

Project: `mcp-harness` — a learning harness for the MCP Python SDK.
An "Order Assistant" MCP server (`server.py`) and a client that exercises it
(`client.py`).

This project is used for **learning**, not just shipping. The workflow below is
mandatory for future sessions.

---

## 1. Record meaningful decisions → `decisions.txt`

Maintain `decisions.txt`. Append an entry whenever you make a meaningful
implementation or architecture decision.

Each entry records:

- **Date** and the change being made.
- **Problem / requirement** being addressed.
- **Approach chosen, and why.**
- **Alternatives considered**, and why they were rejected.
- **Tradeoffs or limitations** accepted.
- **Relevant files and functions.**

For any new dependency, additionally explain: why a library is needed at all,
why this specific one, and whether an existing dependency (or the stdlib) could
have solved it.

Rules:
- Keep entries concise. Record **consequential** decisions, not every small edit.
- **Never** include credentials, tokens, or secrets.
- Append; do not rewrite history. Newest entries at the bottom.

## 2. Document how the code actually executes → `EXECUTION_FLOW.md`

Maintain `EXECUTION_FLOW.md` and keep it aligned with the **implemented** code —
never with intended or planned code.

It must explain:

- How each component starts, including the **exact startup command**.
- Entry points, including ones a framework or CLI manages on our behalf.
- The order of execution for a representative request.
- Which functions call which other functions.
- Where execution crosses a **process or network boundary**.
- How inputs, responses, and errors travel through the system.
- Which behavior **our code** handles vs. what the **SDK/framework** handles.

Rules:
- Reference real file paths and function names (e.g. `server.py:get_order_status`).
- **Clearly label** what was *verified by running it* vs. what is *concluded from
  reading the code*. Use the `[VERIFIED]` / `[INSPECTED]` markers already in the
  file. Never silently upgrade `[INSPECTED]` to `[VERIFIED]`.

After each meaningful change, append a short summary covering:
- What changed in the execution flow.
- Why it changed.
- How it was verified.
- What remains untested.

## 3. Check understanding before accepting major changes

**Before implementing** a major change, briefly state:
1. Its purpose. 2. The proposed approach. 3. The main tradeoff.

**After implementing and testing** it, leave the change in the working tree for
review and **quiz the user** before treating it as accepted.

Quiz format:
- 3–5 short, **open-ended** questions.
- **One at a time.** Wait for the answer before asking the next.
- Cover: the problem the change solves; how execution flows through the changed
  code; why this approach was chosen; and a relevant failure case or limitation.
- **Do not reveal the answer before the user responds.** No hints, no
  multiple-choice, no answering your own question.
- Assess *understanding*, not exact wording.
- If the user misunderstands something, explain it **using the actual code**,
  then ask a **fresh** question re-checking that same concept.

Acceptance:
- Mark the change accepted only after the user demonstrates understanding of the
  key concepts **and explicitly accepts** it.
- Until accepted: **do not commit** the change, and **do not begin another major
  change.**
- Passing the quiz does **not** replace technical testing. Working behavior and
  user understanding are **both** required.

Scope: apply this to meaningful changes. Keep routine fixes lightweight — a
typo, a rename, or a one-line bugfix needs no quiz and no decision entry.
