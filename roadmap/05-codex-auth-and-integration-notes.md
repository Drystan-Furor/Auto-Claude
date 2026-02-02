# Auto-Codex Roadmap — Codex OAuth/Auth + Integration Notes (from docs)

Date: 2026-02-02

Sources:
- https://developers.openai.com/codex/auth
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/mcp
- https://github.com/openai/codex

---

## 1) Authentication primitives we can rely on

Codex supports (for CLI + IDE):
- **Sign in with ChatGPT** (OAuth via browser/device code)
- **Sign in with API key** (NOT desired for this project per requirement)

### Where auth is stored
Codex caches credentials locally:
- plaintext file: `~/.codex/auth.json` (under `CODEX_HOME`, default `~/.codex`)
- OR OS credential store (keyring)

Config option:
- `cli_auth_credentials_store = "file" | "keyring" | "auto"`

Managed environments can enforce:
- `forced_login_method = "chatgpt" | "api"`
- `forced_chatgpt_workspace_id = "..."`

### Headless-friendly auth
- Device code auth: `codex login --device-auth`
- Fallback: login locally, then copy `~/.codex/auth.json`.
- Fallback: SSH port-forward localhost callback (default port `1455`).

**Implication for Auto-Claude:**
- We should NOT reinvent OAuth; instead we should **delegate auth to Codex**.
- Our app should detect whether Codex is authenticated by checking:
  - existence/validity of `~/.codex/auth.json` when `cli_auth_credentials_store=file|auto`
  - or keyring presence when configured.

---

## 2) Codex SDK (TypeScript) exists and is programmatic

Docs: https://developers.openai.com/codex/sdk

- Package: `@openai/codex-sdk`
- Usage model:
  - `const codex = new Codex();`
  - `const thread = codex.startThread();`
  - `await thread.run("...")`
  - can resume thread by ID

**Important:** this is Node.js (>=18) and provides more flexible control than “non-interactive CLI mode”.

**Implication for Auto-Claude:**
- We can implement the new engine as a **Node sidecar service** (or integrate directly in Electron main process) that:
  - runs Codex via the SDK
  - streams events to the Python backend (or replaces it)

This likely avoids fragile CLI stdout parsing.

---

## 3) MCP support in Codex is native

Docs: https://developers.openai.com/codex/mcp

- Codex stores MCP config in TOML:
  - global: `~/.codex/config.toml`
  - project: `.codex/config.toml` (trusted projects)
- CLI management: `codex mcp ...`
- OAuth for MCP servers: `codex mcp login` (per server)

**Implication for Auto-Claude:**
- If we pivot our toolchain toward **Codex-native MCP**, we may not need to re-implement MCP in Python.
- But we must reconcile this with Auto-Claude’s existing tool allowlists and security hooks.

---

## 4) Practical integration options (ranked)

### Option A (recommended): Node Codex SDK engine + Python orchestrator
- Keep Python pipeline (spec files, worktrees, QA loop)
- Replace the Claude Agent SDK client with a provider-neutral adapter that talks to a Node "codex-engine" process
- Node process uses `@openai/codex-sdk` and emits normalized events

Pros:
- No fragile CLI parsing
- Likely best support for threads, streaming, and future features

Cons:
- Requires designing an IPC protocol between Python and Node

### Option B: Drive `codex` CLI non-interactive mode
- Spawn `codex exec ...` or similar
- Parse stdout/stderr

Pros:
- No extra SDK dependency

Cons:
- Harder to make reliable tool-calling + streaming semantics
- Unknown stability across versions

### Option C: Move the entire backend to Node
Pros:
- Single language for SDK + UI

Cons:
- Large rewrite, violates “keep chassis” spirit for near-term

---

## 5) New concrete tasks to add to roadmap (missing today)

1) **Codex auth detector (backend + frontend):**
   - determine if user is logged in via ChatGPT
   - surface status in UI

2) **Provider runtime selection:**
   - `LLM_PROVIDER=codex_oauth` (and optionally keep `claude` during migration)

3) **Codex SDK sidecar / bridge:**
   - implement `codex-engine` in Node
   - define JSON-RPC-ish protocol for:
     - start thread
     - run prompt
     - emit stream events
     - request tool execution (if we keep tools in Python)

4) **Decide tool strategy:**
   - Codex-native MCP vs Auto-Claude tool runner

