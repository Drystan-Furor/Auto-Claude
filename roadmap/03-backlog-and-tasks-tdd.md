# Auto-Codex Roadmap — Backlog & Tasks (TDD-first)

Written as: Senior Backend Software Developer
Approach: TDD, incremental refactor, keep system shippable.

Date: 2026-02-02

---

## Epic 0 — Baseline safety net (tests before refactor)

### Task 0.1 — Add a minimal “engine contract” test harness
**Goal:** create a provider-neutral test harness for streaming/tool calls *without changing behavior yet*.

**Test cases (pytest):**
- `test_session_emits_text_events_in_order()`
- `test_session_requests_tool_and_receives_result()`
- `test_session_handles_tool_error()`

**Implementation notes:**
- Use fake engine + fake tool runner.
- No Claude SDK import in these tests.

---

## Epic 1 — Introduce `LLMEngine` abstraction (Claude remains the engine)

### Task 1.1 — Create `apps/backend/llm/types.py`
Define:
- `StreamEvent` union types
- `ToolCall` (name, input, id)
- `ToolResult` (id, content, is_error)

**Tests:**
- serialization/deserialization if stored
- strict typing + forward compatibility

### Task 1.2 — Create `apps/backend/llm/engine.py` (interface)
**Tests:**
- mypy/typing-level tests (if used)
- a “FakeEngine implements Engine” test

### Task 1.3 — Refactor `agents/session.py` to depend on `LLMEngine`
**Plan:**
- Move Claude SDK–specific streaming parsing into `providers/claude_sdk/engine.py`.
- `agents/session.py` becomes:
  - build prompt
  - call engine
  - when tool requested → call `ToolRunner`
  - feed tool result back to engine

**Tests:**
- existing unit tests should pass
- new harness tests pass

### Task 1.4 — Wrap existing Claude SDK implementation
**Files:**
- `apps/backend/llm/providers/claude_sdk/engine.py`
- `apps/backend/llm/registry.py`

**Tests:**
- a shallow smoke test that engine instantiates given minimal config (no real network)

---

## Epic 2 — Tool execution becomes a first-class backend component

### Task 2.1 — Create `ToolRunner`
**Goal:** unify tool execution across providers.

Responsibilities:
- validate tool inputs (reuse existing `security/*`)
- execute:
  - file ops
  - bash (sandboxed)
  - web fetch/search
  - MCP calls

**Tests:**
- allowlist enforcement: disallow forbidden bash commands
- filesystem restrictions: cannot escape project_dir
- tool result formatting stable

### Task 2.2 — Adapt existing tool registry
Current tools are defined as Agent SDK tools in `agents/tools_pkg/tools/*`.

**Decision point:**
- Either keep Agent SDK tools for Claude and add a parallel non-SDK tool registry for OpenAI, OR
- Extract tool implementations into provider-neutral Python functions and adapt both SDK and OpenAI tool schemas.

**TDD deliverable:**
- At least 3 tools extracted and runnable without Agent SDK:
  - `Read`, `Write`, `Bash`

---

## Epic 3 — Implement OpenAI engine (API transport)

### Task 3.1 — Implement `openai_api` provider
**Scope:**
- Use OpenAI tool calling (Responses API preferred; fallback to Chat Completions if needed).
- Support:
  - streaming text deltas
  - tool call requests
  - continued conversation after tool result

**Tests (contract tests):**
- Run against a mocked OpenAI server or VCR cassette
- Verify tool call roundtrip

**Notes:**
- Keep a compatibility mapping between current tool names and OpenAI function-calling schema.

### Task 3.2 — Add OpenAI config resolution
Add env parsing:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- optional `OPENAI_BASE_URL`

**Tests:**
- invalid config errors are explicit
- missing key produces AuthError

---

## Epic 4 — Implement Codex CLI engine (optional but requested)

### Task 4.1 — Codex CLI adapter
**Goal:** allow engine to run via local `codex` CLI rather than HTTP.

**Assumption:** codex CLI can accept prompts and return streamed output.

**Design:**
- spawn process
- parse stdout into events
- handle tool calls (requires a structured protocol; if CLI cannot do tool calls, restrict to “plan-only” or “no-tools” modes)

**Tests:**
- uses a fake `codex` binary fixture (shell script) for deterministic output

---

## Epic 5 — Frontend: provider selection and OpenAI account support

### Task 5.1 — Introduce provider-agnostic profile model
- Add `OpenAI` as a provider type.
- Store `OPENAI_API_KEY` securely.

**Tests (Vitest):**
- settings store handles OpenAI key
- validation service accepts `sk-...` formats

### Task 5.2 — Update onboarding
- Replace “Sign in with Anthropic” with a provider choice (Anthropic OAuth vs OpenAI API key).

**Tests:**
- onboarding wizard flows for both providers

### Task 5.3 — IPC wiring
- Ensure UI passes provider + credentials to backend runner env.

---

## Epic 6 — Packaging, CI, docs

### Task 6.1 — Packaging scripts update
- Remove `claude_agent_sdk` as a “must exist” check (or keep optional).
- Ensure OpenAI deps are bundled.

### Task 6.2 — Docs
- Update README and guides to explain OpenAI setup.

---

## MVP definition (what we ship first)

- Backend can run a build using `LLM_PROVIDER=openai`.
- Kanban board can launch and complete a task using an OpenAI API key.
- Worktrees/spec outputs/merge flow remain unchanged.

