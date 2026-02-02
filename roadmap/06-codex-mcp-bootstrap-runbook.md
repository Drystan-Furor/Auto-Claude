# Epic 2 / Task 2.1 — Codex MCP bootstrap + runbook

Status: IN PROGRESS
Date: 2026-02-02

This runbook standardizes how Auto-Claude (migrating to Auto-Codex) expects **Codex CLI** to be set up for:
- ChatGPT OAuth auth
- MCP servers (optional, but supported)
- approvals / trusted project config boundaries

Sources:
- Codex auth: https://developers.openai.com/codex/auth
- Codex MCP: https://developers.openai.com/codex/mcp

---

## 0) Preconditions

- Codex CLI installed (macOS/Linux)
  - `npm i -g @openai/codex` OR `brew install --cask codex`
- You have a ChatGPT plan/workspace that includes Codex access

---

## 1) Authenticate Codex via ChatGPT (OAuth)

### Normal (desktop) login
Run:

```bash
codex login
```

Codex opens a browser window; after you sign in, the browser returns an access token to the CLI.

### Headless / remote login (preferred)
Run:

```bash
codex login --device-auth
```

You’ll be shown a link + one-time code to enter in a browser on any device.

### Credential storage
Codex caches credentials either:
- plaintext file: `~/.codex/auth.json` (under `CODEX_HOME`, default `~/.codex`)
- or OS keyring

Config key:

```toml
# file | keyring | auto
cli_auth_credentials_store = "auto"
```

Security note: if using file-based credentials, treat `~/.codex/auth.json` like a password.

---

## 2) MCP configuration overview

Codex MCP config is stored in TOML alongside other Codex config:
- global: `~/.codex/config.toml`
- project-scoped (trusted projects only): `.codex/config.toml`

Codex supports MCP servers:
- **STDIO** (local process)
- **Streamable HTTP** (remote server)

---

## 3) Recommended baseline config.toml (template)

### Global config (suggested)
Create/edit `~/.codex/config.toml`:

```toml
# --- Auth storage ---
cli_auth_credentials_store = "auto"

# Optional: enforce login method in managed envs
# forced_login_method = "chatgpt"  # or "api"

# --- MCP OAuth callback port ---
# Set only if your OAuth provider requires a static callback URI.
# If unset, Codex binds to an ephemeral port.
# mcp_oauth_callback_port = 1455

# --- MCP servers ---
# Example STDIO server
# [mcp_servers.context7]
# command = "npx"
# args = ["-y", "@upstash/context7-mcp"]

# Example HTTP server
# [mcp_servers.figma]
# url = "https://mcp.figma.com/mcp"
# bearer_token_env_var = "FIGMA_OAUTH_TOKEN"
```

### Project-scoped config
For a given Auto-Claude worktree/project, optionally add `.codex/config.toml` in the project root. Only do this if the project is trusted.

---

## 4) Add/manage MCP servers using the CLI

### Add a server

```bash
codex mcp add <server-name> --env VAR1=VALUE1 --env VAR2=VALUE2 -- <stdio server-command>
```

Example (Context7):

```bash
codex mcp add context7 -- npx -y @upstash/context7-mcp
```

### OAuth login for an MCP server

```bash
codex mcp login
```

(Use this for servers that support OAuth.)

### List/help

```bash
codex mcp --help
```

---

## 5) Auto-Claude integration expectation (MVP)

For the MVP “Codex-native tools” approach, Auto-Claude should:
- treat Codex as the executor for file/command operations and MCP tool calls
- avoid re-implementing a Python ToolRunner
- perform **preflight checks** and show actionable errors:
  - Codex installed
  - user authenticated (ChatGPT OAuth)
  - required MCP servers configured (only if we decide MVP needs them)

---

## 6) Open questions (to resolve before we call this DONE)

1) Do we require any MCP servers for MVP?
   - If yes: which ones, and what are their auth requirements?

2) Where should Auto-Claude store “project trust” state?
   - Codex has “trusted projects” concept for `.codex/config.toml`; we should align with that.

3) Should we standardize `mcp_oauth_callback_port` (1455) or leave ephemeral?
   - Static helps SSH port forwarding + restrictive OAuth providers.
   - Ephemeral reduces port conflicts.
