# Cozmo Code — Upgrade Plan

Based on OpenCode UX study (REFERENCE.md) and current Cozmo code audit.

---

## Current state (Phase 4 — baseline)

| Area | Status |
|------|--------|
| CLI | `cozmo code`, `--path`, `--init`, single-shot query |
| Agent | Single CodeAgent, `<tool>` JSON calling, 5-turn loop |
| Tools | `write_file`, `edit_file`, `grep_search`, `run_command` (gated), `git_diff`, `git_log` |
| Index | Chroma project index, respects .gitignore |
| Config | TOML, `code.allow_commands`, model selection |
| Chat | Raw `input()`/`print()` loop, no TUI |

---

## Phase 5 — Quick UX Wins (no TUI framework needed)

Goal: polish the readline experience with high-impact, low-effort patterns.

| # | Feature | Files | Effort |
|---|---------|-------|--------|
| 5.1 | `!cmd` shell passthrough | `cli.py`, `core/code_agent.py` | Very Low |
| 5.2 | `/` slash commands (help, new, exit) | `cli.py` | Very Low |
| 5.3 | `@file` fuzzy file autocomplete | `cli.py` (fzf/python-fzf) | Low |
| 5.4 | Status line (model, tokens, agent) | `cli.py` | Low |
| 5.5 | Config CLI (`cozmo config`) | `cozmo/config_cli.py` | Low |
| 5.6 | `/compact` context compaction | `core/code_agent.py` | Medium |

### 5.1 — `!cmd` shell passthrough
```
If user input starts with "!", run the rest as shell command, return output.
```
**Code**: Add check in `CodeAgent.run()` or `cli.py` loop before calling agent.

### 5.2 — `/` slash commands
```
/help    → show available commands
/new     → clear history
/exit    → quit
/compact → summarize + restart
```
**Code**: Check in cli.py input loop. No model call needed.

### 5.3 — `@file` fuzzy autocomplete
Use `prompt_toolkit` or shell out to `fzf`. On `@` keypress, list project files fuzzy-matched.

### 5.4 — Status line
Before prompt, print one line:
```
[model: ornith:9b | agent: coder | tokens: 1,234 | files: 2]
```

### 5.5 — Config CLI
```
cozmo config show
cozmo config set models.coder qwen3:8b
cozmo config reset
```
Already defined in PLAN.md Phase 5. Move from PLAN to code.

### 5.6 — `/compact` context compaction
When history exceeds N tokens, ask model to summarize oldest messages, replace with summary.

---

## Phase 6 — Multi-Agent System

Goal: Tab-switchable agents (Build ↔ Plan) + custom agents via config.

| # | Feature | Files | Effort |
|---|---------|-------|--------|
| 6.1 | Agent registry | `cozmo/core/agent_registry.py` | Medium |
| 6.2 | PlanAgent (read-only) | `core/plan_agent.py` | Low |
| 6.3 | Agent config via TOML | `config.py` | Low |
| 6.4 | Tab switching | `cli.py` | Low |
| 6.5 | Custom agents via markdown | `core/agent_registry.py` | Medium |
| 6.6 | Agent color/indicator in prompt | `cli.py` | Very Low |

### 6.1 — Agent registry
```python
class AgentRegistry:
    agents: dict[str, type[Agent]]
    
    def create(self, name: str, cfg: dict) -> Agent
    def list_primary(self) -> list[str]
    def list_all(self) -> list[str]
```

### 6.2 — PlanAgent
Extends Agent. Same tool set BUT:
- `edit_file`, `write_file` → gated (always prompt)
- `run_command` → gated (always prompt)
- System prompt: "Analyze code and suggest changes. Do NOT modify files without confirmation."

### 6.3 — Agent config in TOML
```toml
[agents]
primary = ["build", "plan"]

[agents.build]
model = "ornith:9b"
prompt = "You are Cozmo, an expert programmer..."
permissions = { edit = "allow", bash = "ask" }

[agents.plan]
model = "phi4-mini:3.8b"
prompt = "You are Cozmo the architect..."
permissions = { edit = "deny", bash = "deny" }
```

### 6.4 — Tab switching
```
current_agent_idx = (current_agent_idx + 1) % len(primary_agents)
```
Cycle through primary agents. Show which is active in prompt:
```
[build] You: _
```

### 6.5 — Custom agents via markdown
`.cozmo/agents/review.md`:
```yaml
---
name: review
description: Code quality review
model: ornith:9b
permissions:
  edit: deny
  bash: deny
---
You are a code reviewer. Focus on security and performance.
```
Auto-discovered on startup.

---

## Phase 7 — Permission System

Goal: Pattern-based permission gating replacing current binary allow/deny.

| # | Feature | Files | Effort |
|---|---------|-------|--------|
| 7.1 | Permission resolver | `cozmo/core/permissions.py` | Medium |
| 7.2 | Pattern-based bash rules | `tools/code_ops.py` | Low |
| 7.3 | Per-agent permission overrides | `core/agent_registry.py` | Low |
| 7.4 | `--auto` flag | `cli.py` | Low |
| 7.5 | `ask` prompt UX (3 options) | `cli.py` | Low |

### 7.1 — Permission resolver
```python
class PermissionResolver:
    def check(self, tool: str, input: str, agent: str) -> str:
        """Return 'allow', 'ask', or 'deny'"""
```

### 7.2 — Pattern matching
```
bash: { "*": "ask", "git *": "allow", "rm *": "deny" }
edit: { "*.env": "deny", "*": "allow" }
```
Use `fnmatch` for glob matching, last-match-wins.

### 7.3 — Config structure
```toml
[permissions]
"*" = "ask"

[permissions.bash]
"*" = "ask"
"git *" = "allow"
"npm *" = "allow"
"grep *" = "allow"
"rm *" = "deny"

[permissions.edit]
"*" = "allow"
"*.env" = "deny"
```

### 7.4 — `--auto` flag
Skip all `ask` prompts, treat as `allow`.

---

## Phase 8 — Rich TUI

Goal: Replace `input()`/`print()` with proper terminal UI using `textual` or `prompt_toolkit`.

| # | Feature | Files | Effort |
|---|---------|-------|--------|
| 8.1 | Textual TUI shell | `cozmo/tui/` (new package) | High |
| 8.2 | Chat panel | `tui/chat_panel.py` | Medium |
| 8.3 | Input panel with autocomplete | `tui/input_panel.py` | Medium |
| 8.4 | Status bar | `tui/status_bar.py` | Low |
| 8.5 | Diff rendering | `tui/diff_view.py` | Medium |
| 8.6 | Collapsible tool output | `tui/chat_panel.py` | Medium |
| 8.7 | Theme support | `tui/themes/` | Medium |
| 8.8 | Leader key system | `tui/keybinds.py` | High |
| 8.9 | Mouse support | `tui/` (textual built-in) | Low |

### 8.1 — Stack choice: `textual`
- Built-in widgets: scrollable containers, input, tree, tabs, data table
- Async event loop — no blocking on model calls
- CSS-based styling — themes are natural
- Mouse + keyboard unified

### 8.2 — Layout
```
┌─ Header ─────────────────────────────────────┐
│ Cozmo v0.2  │  build  │  model  │  session   │
├──────────────────────────────────────────────┤
│                                              │
│  Chat messages (scrollable)                  │
│  • User: "refactor this"                     │
│  • Cozmo: [used grep_search] → result        │
│  • Cozmo: "Here's the refactored code"       │
│  • [click to expand tool output ▼]           │
│                                              │
├──────────────────────────────────────────────┤
│ > @file.py  !command  /help  [Tab=build]     │
│ ════════════════════════════════════════════  │
│ [agent:build] [model:ornith:9b] [tok:1.2k]   │
└──────────────────────────────────────────────┘
```

---

## Phase 9 — Sessions & State

| # | Feature | Files | Effort |
|---|---------|-------|--------|
| 9.1 | Session persistence (DB) | `cozmo/memory/session_store.py` | Medium |
| 9.2 | Session resume / fork | `cli.py`, `core/code_agent.py` | Medium |
| 9.3 | `/sessions` list & switch | `tui/` | Medium |
| 9.4 | Git-based undo/redo | `tools/code_ops.py`, `core/undo_manager.py` | High |
| 9.5 | Auto-compaction on token limit | `core/code_agent.py` | Medium |
| 9.6 | Session export/import | `cli.py` | Low |
| 9.7 | Session titles (auto-generated) | `core/code_agent.py` | Low |

---

## Phase 10 — Advanced

| # | Feature | Effort | Notes |
|---|---------|--------|-------|
| 10.1 | Subagent delegation (Task tool) | High | Build → spawn @explore for research |
| 10.2 | Custom slash commands via markdown | Medium | `.cozmo/commands/test.md` → `/test` |
| 10.3 | AGENTS.md project rules | Low | Read `AGENTS.md` → inject into system prompt |
| 10.4 | LSP integration | High | Go-to-def, references in chat |
| 10.5 | SKILL.md system | Medium | Loadable skill definitions |
| 10.6 | MCP server support | Very High | External tool protocol |
| 10.7 | Notifications / attention sounds | Low | `tui.json` attention config |

---

## Recommended roadmap

```
Phase 5 ──────────────────────── now
  ├── 5.1  !cmd                (1 hour)
  ├── 5.2  / commands          (1 hour)
  ├── 5.3  @file autocomplete  (3 hours)
  ├── 5.4  status line         (30 min)
  ├── 5.5  config CLI          (2 hours)
  └── 5.6  /compact            (3 hours)

Phase 6 ──────────────────────── next
  ├── 6.1  Agent registry      (2 hours)
  ├── 6.2  Plan agent          (1 hour)
  ├── 6.3  TOML agent config   (1 hour)
  ├── 6.4  Tab switching       (30 min)
  └── 6.5  Custom markdown agents (3 hours)

Phase 7 ──────────────────────── after
  ├── 7.1  Permission resolver (3 hours)
  ├── 7.2  Pattern bash rules  (1 hour)
  ├── 7.3  Per-agent overrides (1 hour)
  ├── 7.4  --auto flag         (30 min)
  └── 7.5  Ask prompt UX       (1 hour)

Phase 8 ──────────────────────── TUI
  ├── 8.1  Textual shell       (8 hours)
  ├── 8.2  Chat panel          (4 hours)
  ├── 8.3  Input + autocomplete(4 hours)
  ├── 8.4  Status bar          (1 hour)
  ├── 8.5  Diff view           (3 hours)
  ├── 8.6  Collapsible output  (2 hours)
  ├── 8.7  Themes              (3 hours)
  ├── 8.8  Leader key system   (4 hours)
  └── 8.9  Mouse               (0 hours — built-in)

Phase 9+ ─────────────────────── stretch
  (as prioritized)
```

---

## Which phase to start?

Vote on order. My recommendation:

**Phase 5 first** — each feature is 1-3 hours, no architectural changes, immediate UX improvement.

Then **Phase 6** (agent switching is the killer feature) and **Phase 7** (permission system is foundation for safety).

Delay **Phase 8** (rich TUI) until UX patterns are validated in readline — the `/`, `@`, `!` conventions work identically in both modes, so you can build them now and port later.
