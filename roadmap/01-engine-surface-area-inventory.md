# Auto-Codex Roadmap — Engine Surface Area Inventory (what must change)

This file identifies the **real integration points** (“engine coupling”) that must be changed to make Auto-Claude run on OpenAI/Codex.

Date: 2026-02-02

---

## A) Backend (Python) — primary coupling

### 1) Client construction & security envelope
- `apps/backend/core/client.py`
  - builds `.claude_settings.json`
  - instantiates `ClaudeSDKClient(options=ClaudeAgentOptions(...))`
  - configures:
    - tool allowlist (`allowed_tools`)
    - MCP servers (`mcp_servers`)
    - hooks (`PreToolUse` Bash validator)
    - working directory + file permission rules

This is the *central engine adapter* today.

### 2) Session execution (streaming + tool calls)
- `apps/backend/agents/session.py`
  - consumes SDK message stream (`client.query(...)`, `client.receive_response()`)
  - drives tool execution via SDK integration

Anything provider-specific in session streaming/tool execution must be abstracted.

### 3) Planner/coder/QA orchestrators
These call `create_client()` and assume SDK semantics:
- `apps/backend/agents/coder.py`
- `apps/backend/agents/planner.py`
- `apps/backend/qa/reviewer.py`
- `apps/backend/qa/fixer.py`
- `apps/backend/qa/loop.py`
- plus runners: `apps/backend/runners/**`

### 4) Tooling layer (Agent SDK tools + MCP)
- `apps/backend/agents/tools_pkg/**`
  - registers tools using `claude_agent_sdk.tool`
  - config chooses tools per phase/agent type
  - MCP server selection: context7/electron/puppeteer/linear/graphiti/auto-claude

OpenAI engine must support *equivalent tool calling* or we must provide a compatibility layer that executes tools and returns results.

### 5) Auth assumptions
- backend currently oriented to Claude Code CLI OAuth/token discovery:
  - `core/auth.py` (ensure oauth token, env vars like CLAUDE_CONFIG_DIR)

For OpenAI:
- auth becomes API key based (`OPENAI_API_KEY`) and optionally project/org.
- Codex CLI auth may also exist (if using `codex` CLI); define a single canonical backend auth source.

---

## B) Frontend (Electron/React) — secondary coupling

### 1) “Claude accounts / profiles” domain
- `apps/frontend/src/main/claude-profile/**`
- `apps/frontend/src/preload/api/terminal-api.ts` + IPC channels referencing claude profiles
- Onboarding content explicitly references “Sign in with Anthropic” and “Claude Code”

To support OpenAI:
- either generalize to **LLM provider profiles** (Claude/OpenAI/Other)
- or introduce a parallel “OpenAI profile manager” then unify later.

### 2) Rate limit / usage monitoring
- `apps/frontend/src/main/claude-profile/usage-monitor.ts`
  - includes Anthropic OAuth usage endpoint behavior

To support OpenAI:
- implement OpenAI usage retrieval OR simplify: track locally by request cost/tokens.

### 3) API Profile UI
The UI already supports “custom Anthropic-compatible endpoints” and key validation.
- `apps/frontend/src/main/services/profile-service.ts` uses `@anthropic-ai/sdk`.

For OpenAI:
- add OpenAI base URL / model list checks using OpenAI endpoints
- update provider detection + validation

---

## C) Build/packaging coupling

- Frontend packaging bundles backend + python runtime site-packages.
- Linux package verification expects `claude_agent_sdk` present.

To support OpenAI:
- update packaging scripts/tests to include OpenAI deps and (optionally) drop claude SDK from required set.

---

## D) Key migration risk areas

1. **Tool execution semantics**: Agent SDK provides a specific tool calling model. OpenAI tool calling differs.
2. **Streaming protocol**: UI expects progress logs and tool boundaries.
3. **Security**: we must not regress on sandbox/allowlist.
4. **Provider selection** across CLI and UI.

---

## E) Definition of done for “Auto-Codex MVP”

- Can create a task in Kanban.
- Backend runs spec pipeline + coding loop using OpenAI credentials.
- QA loop runs and produces `qa_signoff`.
- Worktree merge/review works unchanged.
- No Anthropic token required.

