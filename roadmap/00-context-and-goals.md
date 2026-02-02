# Auto-Codex Roadmap — Context & Goals

Owner goal: replace the **Anthropic/Claude engine** in Auto-Claude with an **OpenAI engine** (Codex / Codex CLI / OpenAI API) while preserving the **chassis** (Kanban UI, worktree isolation, spec pipeline, QA loop, terminals).

Date: 2026-02-02

---

## What “engine” vs “chassis” means in this repo

### Chassis (keep)
- **Frontend (Electron/React):** Kanban board, terminal grid, task UI, worktree UX, settings, onboarding.
- **Spec/workflow artifacts:** `.auto-claude/specs/*` directory format (spec.md, requirements.json, implementation_plan.json, qa_report.md, etc.).
- **Worktree manager:** `.auto-claude/worktrees/tasks/{spec-name}` branch model (`auto-claude/{spec-name}`).
- **Execution orchestration:** planning → coding loop → QA loop → merge/review.
- **Security model:** sandboxing + tool allowlist + filesystem restrictions.

### Engine (replace)
- **LLM client:** currently Claude Agent SDK (`claude_agent_sdk`, `ClaudeSDKClient`, `ClaudeAgentOptions`) plus Claude Code CLI auth assumptions.
- **Tool protocol / tool execution:** currently follows Agent SDK “tools” and MCP servers.
- **Auth + profile management:** Claude OAuth tokens, CLAUDE_CONFIG_DIR semantics, rate limit detection tied to Anthropic usage endpoints.

---

## Hard constraints / acceptance criteria

1. **Kanban tasks must run end-to-end using an OpenAI account** (no Anthropic dependency required).
2. **Backend must support a provider switch** (at minimum: `claude` and `openai` engines during migration).
3. Preserve:
   - isolated worktrees
   - spec pipeline outputs
   - QA loop semantics (approve/reject signoff)
   - ability to run in UI and CLI modes
4. **TDD-first migration**: every refactor introduces tests to lock behavior.
5. **No vendor lock-in**: OpenAI engine should be designed as a provider plugin, not a hard replace.

---

## Why this needs an abstraction layer

In the backend, the Claude Agent SDK is deeply integrated (client creation, tool allowlists, streaming, MCP servers).
A direct “replace imports” approach will destabilize:
- tool execution
- streaming UI logs
- error handling & retry (tool concurrency)
- profile switching

Therefore we introduce a **provider-agnostic LLM Engine interface** and migrate call sites gradually.

---

## Migration approach (high level)

Phase 1 (Safety):
- Add an `LLMEngine` abstraction and tests around existing behaviors.

Phase 2 (Parallel engines):
- Implement an OpenAI/Codex engine and run the same pipeline through it.

Phase 3 (UI swap + profile/auth):
- Add “OpenAI” profiles in UI + wire env/config to backend.

Phase 4 (Remove lock-in):
- Make Claude optional, modularize provider-specific components.

---

## Non-goals (for first milestone)
- Perfect feature parity with Claude Code CLI UX (multi-account switching, oauth refresh).
- Supporting every OpenAI model variant.
- Rewriting the UI beyond provider selection + auth.

