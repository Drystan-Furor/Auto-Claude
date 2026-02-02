# Auto-Codex Roadmap — Target Architecture (OpenAI engine, keep chassis)

This proposes a provider-agnostic architecture to support **OpenAI (Codex/Codex CLI/API)** without breaking the existing pipeline.

Date: 2026-02-02

---

## 1) Core design: `LLMEngine` interface

Introduce a new backend module:

```
apps/backend/llm/
  engine.py              # Protocol / ABC
  types.py               # Message, ToolCall, ToolResult, StreamEvent
  errors.py              # RateLimitError, AuthError, etc.
  registry.py            # get_engine(provider, config)
  providers/
    claude_sdk/          # adapter around existing claude_agent_sdk
    openai_api/          # OpenAI Responses/ChatCompletions tool calling
    codex_cli/           # optional: drive codex CLI as a transport
```

### Engine responsibilities
- `start_session(...)` / `run(prompt, tools, ...)` returning a stream of events.
- emit events normalized as:
  - `TextDelta`
  - `ToolCallRequested`
  - `ToolResultReceived`
  - `UsageUpdated`
  - `SessionCompleted`
  - `SessionFailed`

### Tool execution contract
We keep a single “tool runner” that:
- validates inputs (security constraints)
- executes tool (file ops, bash, web fetch/search, MCP)
- returns a `ToolResult`

Engine only needs to request tools; orchestrator executes them.

---

## 2) “Chassis compatibility layer”

We do **not** rewrite:
- spec pipeline
- worktrees
- QA signoff contract
- implementation_plan.json schema

Instead we refactor `agents/session.py` to depend on `LLMEngine` and a `ToolRunner`.

### Where it plugs in
- `core/client.py` becomes provider-neutral `llm/registry.py` + security config generator.
- `agents/session.py` becomes provider-neutral stream driver.
- Orchestrators (`coder.py`, `planner.py`, `qa/*`) remain mostly unchanged.

---

## 3) Provider configs & env vars

Add unified provider config in `.auto-claude/.env` (project-level) or global config:

- `LLM_PROVIDER=claude|openai|codex_cli`

OpenAI API:
- `OPENAI_API_KEY=...`
- `OPENAI_BASE_URL=https://api.openai.com/v1` (optional)
- `OPENAI_MODEL=o3-mini|gpt-5|...`

Codex CLI:
- `CODEX_CLI_PATH=codex`
- `CODEX_MODEL=...` (if CLI supports)
- `CODEX_ENV_*` (whatever codex CLI needs)

**Important:** backend should accept provider settings via CLI args and via UI IPC config.

---

## 4) Frontend changes (provider-agnostic profiles)

Replace Claude-specific “profiles” with “LLM profiles”:
- Provider: `anthropic_oauth`, `anthropic_api`, `openai_api`, `openrouter`, etc.
- Credential store semantics differ:
  - OpenAI: key in keychain/credential manager
  - Anthropic OAuth: refresh token flow

MVP approach:
- Add OpenAI profile type in parallel to Claude profiles.
- Update onboarding to allow OpenAI selection.
- Update settings UI to manage OpenAI API keys.

---

## 5) Test strategy (TDD)

We use tests to lock in:
- existing JSON artifacts (spec + plan schema)
- worktree semantics
- tool security behavior
- session event stream

Then implement OpenAI engine behind same interface.

---

## 6) Milestones

M1: Backend abstraction + Claude adapter (no behavior change)
M2: OpenAI API adapter + basic tool calling
M3: Frontend provider selection + OpenAI auth UI + IPC wiring
M4: Packaging + docs + remove hard dependency on Claude

