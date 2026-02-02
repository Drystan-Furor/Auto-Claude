# Auto-Codex Roadmap — Detailed Task Breakdown (files to touch)

This is the practical “diff plan”: where to make changes, and what to write tests for.

Date: 2026-02-02

---

## 1) Backend: create a provider-neutral LLM layer

### New modules (backend)
Create:
- `apps/backend/llm/engine.py`
- `apps/backend/llm/types.py`
- `apps/backend/llm/errors.py`
- `apps/backend/llm/registry.py`

Provider adapters:
- `apps/backend/llm/providers/claude_sdk/engine.py`
- `apps/backend/llm/providers/openai_api/engine.py`
- (optional) `apps/backend/llm/providers/codex_cli/engine.py`

### Refactor touchpoints
- `apps/backend/core/client.py`
  - keep security policy generation
  - move provider-specific construction to `llm/registry.py`

- `apps/backend/agents/session.py`
  - replace direct `claude_agent_sdk` streaming with provider-neutral events

- `apps/backend/agents/coder.py`, `planner.py`, `qa/*`
  - should call `registry.get_engine(...)` or a new provider-neutral `create_engine(...)`

### Tests to add (pytest)
- `apps/backend/tests/test_llm_engine_contract.py`
- `apps/backend/tests/test_tool_runner_security.py`
- `apps/backend/tests/test_openai_engine_tool_roundtrip.py` (can be mocked)

---

## 2) Backend: tool runner extraction

### Current state
Tools are defined via Agent SDK decorators in:
- `apps/backend/agents/tools_pkg/tools/*.py`

### Target state
Extract implementations to provider-neutral functions:
- `apps/backend/tools/` (new)
  - `filesystem.py` (Read/Write/Edit/Glob/Grep)
  - `bash.py` (sandboxed, allowlist)
  - `web.py` (fetch/search)
  - `mcp.py` (MCP calls)

Then:
- Claude SDK adapter exposes these as SDK tools.
- OpenAI engine exposes the same schema as OpenAI function tools.

### Tests
- `test_bash_allowlist_blocks_rm_rf()` (example)
- `test_fs_read_denies_escape_path()`

---

## 3) Backend: Auth + config

### Add provider config
Add parsing:
- `LLM_PROVIDER`
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`

Keep existing:
- `CLAUDE_*` env vars

### Tests
- `test_config_requires_openai_key_when_provider_openai()`

---

## 4) Frontend: provider-agnostic account support

### High-impact areas
- `apps/frontend/src/main/claude-profile/*` (rename/generalize)
- `apps/frontend/src/main/services/profile-service.ts` (currently uses `@anthropic-ai/sdk`)
- `apps/frontend/src/main/api-validation-service.ts` (already mentions OpenAI)
- Onboarding components:
  - `apps/frontend/src/renderer/components/onboarding/AuthChoiceStep.tsx`
  - i18n keys under `apps/frontend/src/shared/i18n/locales/*`

### Minimum viable approach
- Keep existing Claude OAuth path.
- Add “OpenAI API Key” path.
- Store OpenAI key.
- UI uses provider selection to spawn backend processes with correct env vars.

### Tests
- Vitest tests for:
  - provider selection state
  - validation of OpenAI keys
  - IPC env assembly

---

## 5) Packaging/CI updates

### Scripts to inspect/modify
- `apps/frontend/scripts/download-python.cjs`
- `apps/frontend/scripts/verify-python-bundling.cjs`
- `apps/frontend/scripts/verify-linux-packages*`

Goal:
- Ensure bundled python contains the OpenAI engine deps.
- Stop failing builds if `claude_agent_sdk` is optional.

---

## 6) Open questions (need decisions)

1. **Do we require Codex CLI, OpenAI API, or both?**
   - API is straightforward for tool calling.
   - CLI may not support structured tool calls.

2. **Do we keep MCP toolchain?**
   - If OpenAI engine supports calling MCP via backend tool runner, yes.
   - Otherwise, limit initial OpenAI MVP to core tools only.

3. **Token/usage monitoring for OpenAI**
   - Implement via OpenAI usage endpoints or local accounting.

