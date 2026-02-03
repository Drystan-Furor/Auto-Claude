# Auto-Codex Roadmap — Backlog & Tasks (TDD-first)

Written as: Senior Backend Software Developer
Approach: TDD, incremental refactor, keep system shippable.

Date: 2026-02-02

---

## Epic 0 — Baseline safety net (tests before refactor)

### Task 0.1 (DONE) — Add a minimal “engine contract” test harness
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

### Task 1.1 (DONE) — Create `apps/backend/llm/types.py`
Define:
- `StreamEvent` union types
- `ToolCall` (name, input, id)
- `ToolResult` (id, content, is_error)

**Tests:**
- serialization/deserialization if stored
- strict typing + forward compatibility

### Task 1.2 (DONE) — Create `apps/backend/llm/engine.py` (interface)
**Tests:**
- mypy/typing-level tests (if used)
- a “FakeEngine implements Engine” test

### Task 1.3 (DONE) — Refactor `agents/session.py` to depend on `LLMEngine`
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

### Task 1.4 (DONE) — Wrap existing Claude SDK implementation
**Files:**
- `apps/backend/llm/providers/claude_sdk/engine.py`
- `apps/backend/llm/registry.py`

**Tests:**
- a shallow smoke test that engine instantiates given minimal config (no real network)

---

## Epic 2 — Re-scope: Codex-native tools + approvals (minimal backend ToolRunner)

**Decision:** Prefer **Codex-native** tool execution (MCP + Codex approvals) as much as possible.

**What changes:**
- We do **not** build a full provider-neutral Python ToolRunner as the primary execution path.
- Instead, we ensure the chassis can:
  - configure Codex (auth, trusted projects, config.toml)
  - set up MCP servers
  - rely on Codex’s approvals + allow/deny lists
  - observe/report tool activity at a high level (for UX + audit) without re-implementing tool semantics.

### Task 2.1 (DONE) — Codex MCP bootstrap + runbook
**Goal:** make it easy and repeatable for a user/workspace to get the same tool surface.

Deliverables:
- A documented baseline `~/.codex/config.toml` (and `.codex/config.toml` for trusted projects)
- Recommended MCP servers for MVP (or explicitly “none”)
- Document OAuth flows:
  - `codex mcp login` for MCP servers
  - `codex login --device-auth` for headless

**Tests:**
- lightweight config parsing/validation tests in backend (if we read config)
- smoke doc checklist (manual) for “fresh machine can run Codex with MCP”

### Task 2.2 (DONE) — Security + approvals alignment
**Goal:** map Auto-Claude’s security model to Codex controls.

Deliverables:
- Document how Auto-Claude restrictions translate to:
  - Codex approval modes
  - MCP enabled_tools/disabled_tools
  - trusted project boundaries
- Add backend-side preflight checks (non-invasive):
  - Codex installed
  - user authenticated (ChatGPT OAuth)
  - required MCP servers configured (if any)

**Tests:**
- unit tests for preflight checks and error messaging

### Task 2.3 (DONE) — Tool visibility (observability), not tool execution

### Task 2.4 — Future: move Codex preflight to the Codex engine/provider (enforced centrally)
**Goal:** ensure *any* Codex-backed run cannot start without passing preflight.

Rationale:
- Option A (current): preflight lives at the orchestrator entrypoint (`run_autonomous_agent`).
- Option C (future): preflight lives inside the Codex engine/provider implementation, so *all* call sites are covered (builds, planner, reviews, spec pipeline, etc.).

Deliverables:
- Codex engine/provider calls `codex_preflight()` (or equivalent) before first execution
- Unified error surface (CLI + UI)

Tests:
- unit test that Codex engine refuses to start if preflight fails

**Goal:** surface “what tools were used” to the UI/logs without executing tools in Python.

Deliverables:
- minimal event mapping for:
  - tool call started
  - tool call completed (success/error)
- persisted logs that can be shown in the Kanban/task UI

**Tests:**
- contract tests that tool events are emitted in-order and are stable

---

## Epic 3 — Implement OpenAI engine (API transport)

### Reality check (2026-02-03)
What we implemented so far:
- Added `apps/backend/llm/providers/openai_api/engine.py` (`OpenAIAPIEngine`) using **Responses API streaming**.
  - Maps `response.output_text.delta` → `TextEvent`
  - Maps function call args streaming → `ToolCallEvent`
  - Supports `send_tool_result()` via `function_call_output` + `previous_response_id`
- Added OpenAI env config parsing in `openai_api/config.py`.
  - Missing `OPENAI_API_KEY` raises **AuthError** (new shared `llm/errors.py`).
- Wired OpenAI selection in **spec pipeline runner** (`spec/pipeline/agent_runner.py`) when `LLM_PROVIDER=openai`.
  - Current limitation: tool calls in this runner are **not executed yet**; we fail clearly if a tool is requested.
- Test infra insight:
  - The repo’s async tests require `pytest-asyncio`.
  - Added `pytest.ini` with `asyncio_mode=auto`.

What remains for MVP:
- The MVP definition requires the **build loop** (not only spec pipeline) to run under `LLM_PROVIDER=openai`.
- We still need a stable strategy for tool-calling:
  - Either implement a minimal provider-neutral ToolRunner (Epic 1.3 intent), or
  - Define an OpenAI-specific tool execution path (and later align with Codex-native tools).

---

### Task 3.0 (NEW) — Ensure async test support in backend
**Goal:** running pytest locally should support async contract tests.

Deliverables:
- Add `pytest-asyncio` as a backend test dependency
- Add `pytest.ini` to configure `asyncio_mode=auto` and register the `asyncio` mark

Tests:
- `pytest -q llm/providers/openai_api` runs without plugin errors

---

### Task 3.1 — Implement `openai_api` provider
**Status:** PARTIAL (engine skeleton + fake-client contract tests exist)

**Scope:**
- Use OpenAI tool calling (Responses API preferred; fallback to Chat Completions if needed).
- Support:
  - streaming text deltas
  - tool call requests
  - continued conversation after tool result

**Done:**
- Responses streaming → provider-neutral events
- Tool-call roundtrip logic (via `send_tool_result()`)

**Remaining:**
- Add contract tests against a mocked HTTP server or VCR cassette (real API surface)
- Add Chat Completions fallback if Responses API isn’t available
- Decide/tool mapping contract: OpenAI tool schema ↔ Auto-Claude tool registry

**Notes:**
- Keep a compatibility mapping between current tool names and OpenAI function-calling schema.

### Task 3.2 — Add OpenAI config resolution
**Status:** DONE (env parsing + explicit AuthError)

Add env parsing:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- optional `OPENAI_BASE_URL`

**Tests:**
- invalid config errors are explicit
- missing key produces AuthError

---

### Task 3.3 (NEW) — Wire OpenAI provider into the main build loop
**Goal:** meet MVP requirement “Backend can run a build using `LLM_PROVIDER=openai`”.

Deliverables:
- The main agent session/chassis (build + QA) should instantiate engines through `llm.registry.create_engine()` based on `LLM_PROVIDER`.
- Ensure OpenAI uses the same logging/observability mapping (`llm/observability.py`).

Tests:
- A small integration test that runs a minimal “turn” through the build loop with a fake OpenAI client.

---

### Task 3.4 (NEW) — Decide and implement tool execution strategy for OpenAI
**Goal:** when OpenAI requests a tool call, the system can execute it and continue.

Options (pick one for MVP):
- **A) Minimal provider-neutral ToolRunner** (aligns with Epic 1.3 intent)
  - Execute existing tools (MCP hooks / bash sandbox) and feed results back.
- **B) OpenAI-only tool executor**
  - Provide a narrow mapping for a small allowlist of tools used in MVP.

Deliverables:
- Tool name + JSON schema mapping (Auto-Claude tool registry → OpenAI function definitions)
- Tool call → execution → `ToolResult` → `send_tool_result()` loop

Tests:
- Contract test: tool call requested → tool executed → engine continues and produces text

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

