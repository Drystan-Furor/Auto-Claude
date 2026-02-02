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

### Task 2.3 — Tool visibility (observability), not tool execution

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

