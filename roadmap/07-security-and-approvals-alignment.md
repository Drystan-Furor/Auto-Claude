# Epic 2 / Task 2.2 — Security + approvals alignment (Auto-Claude ↔ Codex)

Status: IN PROGRESS
Date: 2026-02-02

Goal: map Auto-Claude’s existing security model to **Codex-native** controls:
- Codex approval modes (what requires user confirmation)
- MCP server allow/deny lists (`enabled_tools` / `disabled_tools`)
- trusted project boundaries for `.codex/config.toml`
- managed config enforcement knobs (when relevant)

Sources:
- Codex auth: https://developers.openai.com/codex/auth
- Codex MCP: https://developers.openai.com/codex/mcp

---

## 1) Current Auto-Claude security surfaces (inventory)

From the existing codebase, Auto-Claude security is enforced primarily via:

- **bash security hook** (`apps/backend/security/*`, referenced by `core/client.py`)
  - blocks dangerous commands
  - enforces allowlists / patterns

- **tool input validation** (`security/tool_input_validator.py`)
  - sanitizes and truncates tool inputs for display

- **MCP server validation** (`core/client.py::_validate_custom_mcp_server`)
  - restricts allowed `command` values
  - restricts dangerous flags
  - prevents “shell as mcp server” style command injection

- **tool allowlists per phase** (via `agents/tools_pkg/*`)

We should preserve the *intent* of these controls while moving execution to Codex.

---

## 2) Codex-native controls we should rely on

### 2.1 Approvals UX
Codex provides built-in approvals (especially around tool calls / MCP tool calls).

**Strategy:**
- Prefer configuring approval strictness in Codex rather than reproducing a Python-side “approve tool call” flow.

> TODO: Add exact Codex config key(s) for approval mode once we capture it from Codex CLI `--help` or official docs section.

### 2.2 MCP tool allow/deny
Codex MCP supports:
- `enabled_tools` allow list
- `disabled_tools` deny list (applied after enabled_tools)

This gives us a provider-native way to restrict what MCP tools are callable.

### 2.3 Trusted projects boundary
Codex supports project-scoped `.codex/config.toml` only for trusted projects.

**Strategy:**
- Auto-Claude should align its “project/worktree trust” concept with Codex trusted projects.
- When Auto-Claude creates worktrees, it should be explicit whether the worktree is treated as trusted.

---

## 3) Mapping: Auto-Claude intent → Codex configuration

### 3.1 “Don’t run destructive shell commands”
Auto-Claude today blocks destructive `bash`.

With Codex-native execution, we should:
- rely on Codex approval prompts for shell execution
- optionally run Codex in a stricter approval mode for command execution

**Open question:** do we need an additional wrapper that blocks known-dangerous commands *before* Codex runs them?
- If yes, this becomes a “preflight policy layer” (not a full ToolRunner)
- If no, we rely on approvals + user discretion

### 3.2 “Tools must not escape project directory”
Auto-Claude enforces this by controlling tool implementations.

With Codex-native execution:
- Codex operates in a chosen working directory.
- We should standardize that all runs start inside the worktree root.

**Mitigation:**
- ensure the Codex invocation sets cwd to the worktree
- document to not trust projects that contain secrets outside repo

### 3.3 “MCP servers must be safe to start”
Auto-Claude validates MCP server config (command allowlist).

With Codex-native MCP:
- Codex itself starts MCP servers defined in config.toml.

**Mitigation:**
- keep Auto-Claude-side validation for any configuration that Auto-Claude generates/edits
- do not accept arbitrary user-provided MCP server specs without validation

---

## 4) Backend-side preflight checks (non-invasive)

Even with Codex doing the work, Auto-Claude should fail fast with actionable errors.

Proposed checks:
1) Codex binary exists (`codex --version`)
2) Auth present:
   - if `cli_auth_credentials_store=file|auto`: check `~/.codex/auth.json` exists
   - otherwise: instruct user to set `cli_auth_credentials_store="file"` or log in
3) If MVP requires MCP servers:
   - check `~/.codex/config.toml` has required `[mcp_servers.<name>]` entries

> Implementation note: these checks must not read/print token contents.

---

## 5) TDD plan for this task

### Unit tests
- `test_codex_preflight_missing_binary_shows_actionable_error()`
- `test_codex_preflight_missing_auth_shows_login_instructions()`
- `test_codex_preflight_does_not_log_token_contents()`
- `test_codex_preflight_mcp_required_missing_config_fails()` (only if we require MCP servers)

### Non-goals
- Implementing actual tool execution in Python
- Replacing Codex approvals UI

---

## 6) Inputs we still need to capture

1) Codex approval-mode config keys (from official docs or `codex` help output)
2) Whether MVP requires any MCP server(s)
3) How Auto-Claude should persist “trusted project” decisions (and whether it should automate `.codex/config.toml` writes)
