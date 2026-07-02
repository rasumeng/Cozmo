# OpenCode Reference — UI/UX Patterns for Cozmo

Study of OpenCode's terminal interface, agent system, commands, and workflows.
Source: opencode.ai/docs (June 2026). Not for copying — for inspiration.

---

## 1. Entry Points & Modes

### 1.1 TUI (default)
```
opencode                    # interactive TUI in CWD
opencode /path/to/project   # TUI in specific dir
opencode --continue         # resume last session
opencode --session <id>     # resume specific session
opencode --fork             # fork session on resume
opencode --agent <name>     # start with specific agent
opencode --auto             # auto-approve permissions
opencode --model "p/m"      # start with specific model
```

### 1.2 Non-interactive (CLI)
```
opencode run "query"                          # single-shot
opencode run --attach http://localhost:4096    # attach to running server
opencode run --file file1.ts --file file2.ts   # attach files
opencode run --continue "follow-up question"   # continue last session
opencode run --agent <name> "query"            # with specific agent
opencode run --format json "query"             # raw JSON events output
```

### 1.3 Headless server
```
opencode serve              # HTTP API server
opencode web                # HTTP + Web UI
opencode acp                # Agent Client Protocol (stdin/stdout ndjson)
opencode attach <url>       # attach TUI to remote backend
```

### 1.4 Session management
```
opencode session list       # list all sessions
opencode session delete <id>
opencode export <id>        # export as JSON
opencode import <file|url>  # import session
opencode stats              # token usage + cost stats
```

### 1.5 Key insight for Cozmo
- **Single binary, multiple personalities**: `opencode` → TUI, `opencode run` → headless, `opencode serve` → API.
- Cozmo could keep `cozmo code` as TUI, add `cozmo --auto` flag, and `cozmo run` already exists for headless.

---

## 2. TUI Layout

### 2.1 Screen zones
```
┌─ Header Bar ──────────────────────────────────────┐
│ version │ agent mode │ session status │ provider    │
├────────────────────────────────────────────────────┤
│                                                    │
│  Chat Panel (scrollable message history)           │
│  • User messages with username toggle              │
│  • Assistant responses with tool execution details │
│  • Collapsible tool call output                    │
│  • Thinking/reasoning blocks (toggleable)          │
│                                                    │
├────────────────────────────────────────────────────┤
│ Input Area (prompt entry)                          │
│ • @ fuzzy file autocomplete                       │
│ • ! shell command prefix                          │
│ • / slash commands                                │
│ • Tab autocomplete                                 │
├────────────────────────────────────────────────────┤
│ Status Bar                                         │
│ model │ agent │ files modified │ token count │ menu │
└────────────────────────────────────────────────────┘
```

### 2.2 Key UX affordances
- **Tool details toggle** (`/details`): expand/collapse tool execution output inline.
- **Username toggle**: hide username in chat for cleaner output.
- **Thinking blocks** (`/thinking`): show/hide model reasoning (when supported).
- **Diff rendering**: `auto` (adapts to width) or `stacked` (single column).
- **Scroll acceleration**: macOS-style natural scrolling.
- **Mouse support**: toggleable (`mouse: true/false` in `tui.json`).
- **Timestamps** toggle per message.

### 2.3 Key insight for Cozmo
- Cozmo currently uses raw `print()` + `input()`. A proper TUI would use something like `textual`, `prompt_toolkit`, or `rich` for:
  - Scrollable history
  - Inline collapsible tool output
  - Status bar
  - Better diffs

---

## 3. Agent System

### 3.1 Agent types

| Type | Tab-able? | Purpose | Example |
|------|-----------|---------|---------|
| Primary | Yes (Tab) | Main conversation agents | **Build**, **Plan** |
| Subagent | No (via @task tool) | Specialized helpers | **General**, **Explore**, **Scout** |
| Hidden | No | System tasks | Compaction, Title, Summary |

### 3.2 Built-in agents

| Agent | Mode | Permissions | Use case |
|-------|------|-------------|----------|
| **Build** | primary | all tools allowed | Default dev work |
| **Plan** | primary | edit=ask, bash=ask | Analysis, planning, no changes |
| **General** | subagent | all except todo | Multi-step tasks, research |
| **Explore** | subagent | read-only | Fast codebase exploration |
| **Scout** | subagent | read-only | External dependency research |
| Compaction | primary (hidden) | system | Context compaction |
| Title | primary (hidden) | system | Generate session titles |
| Summary | primary (hidden) | system | Session summarization |

### 3.3 Switching agents
- **Tab** — cycle forward through primary agents
- **Shift+Tab** — cycle backward
- **@mention** — invoke subagent manually (e.g., `@explore find this function`)
- **Primary agents auto-invoke** subagents via `task` tool when relevant
- **Ctrl+A** — list all agents
- Custom `switch_agent` keybind configurable

### 3.4 Subagent session nesting
```
Parent session (Build/Plan agent)
  ├── Child session 1 (from @general invoke)
  ├── Child session 2 (from another @general invoke)
  └── Back to parent
```
- `Leader + Down` — enter first child session
- `Right` — cycle to next child
- `Left` — cycle to previous child
- `Up` — return to parent

### 3.5 Custom agents (Markdown)
```
~/.config/opencode/agents/review.md
---
description: Reviews code for best practices  
mode: subagent  
model: anthropic/claude-sonnet-4-20250514  
temperature: 0.1  
permission:  
  edit: deny  
  bash: deny  
---
You are in code review mode. Focus on...
```

- File name = agent name (`review.md` → `review` agent)
- Places: `~/.config/opencode/agents/` (global) or `.opencode/agents/` (project)
- Can also define in `opencode.json` under `agent` key

### 3.6 Agent config options
- `description` — required, shown to model
- `mode` — `primary`, `subagent`, or `all`
- `model` — override model for this agent
- `temperature` — 0.0–1.0
- `top_p` — 0.0–1.0
- `steps` — max agentic iterations before forced text response
- `permission` — per-tool allow/ask/deny (overrides global)
- `hidden` — hide from @ autocomplete (subagents only)
- `color` — hex or theme color name
- `prompt` — path to custom system prompt file (`{file:./prompts/build.txt}`)
- `disable` — true/false
- Additional fields pass through to provider (e.g., `reasoningEffort`)

### 3.7 Key insight for Cozmo
- **Build ↔ Plan as Tab-switchable agents** is Cozmo's most obvious first target.
- Cozmo already has specialist prompts (chat/coder/vision/research) — these map naturally to primary/subagent concepts.
- Custom agents via SKILL.md or markdown config is a natural extension.
- The `task` tool for subagent delegation is powerful — Cozmo could use `task` for parallel research while coding.

---

## 4. Input System

### 4.1 Prefixes

| Prefix | Effect | Example |
|--------|--------|---------|
| `@file` | Fuzzy file search → attach content | `@src/main.ts` |
| `@alias` | Reference root → attach as context | `@docs` |
| `@alias/file` | File inside reference | `@sdk/src/client.ts` |
| `!command` | Run shell, add output to conversation | `!npm test` |
| `/command` | Slash command | `/new`, `/help` |

### 4.2 @ autocomplete
- Fuzzy file matching in CWD
- Shows file paths, sorts by relevance
- Configured references also appear (`@docs`, `@sdk/...`)
- `hidden: true` omits from autocomplete but still available programmatically

### 4.3 References (external directories)
```jsonc
{
  "references": {
    "docs": { "path": "../product-docs", "description": "..." },
    "sdk": { "repository": "anomalyco/opencode-sdk-js", "branch": "main" }
  }
}
```
- Local directores via `path`
- Git repos via `repository` (auto-cloned into cache)
- `description` tells model when to use it
- Auto-allowed through external_directory permission

### 4.4 Multi-line input
- `Shift+Enter` — insert newline
- `Enter` — submit
- Editor mode: `/editor` opens `$EDITOR` for composing

### 4.5 Input editing (Readline/Emacs keys)
| Shortcut | Action |
|----------|--------|
| Ctrl+A | Line start |
| Ctrl+E | Line end |
| Ctrl+U | Delete to line start |
| Ctrl+K | Delete to line end |
| Ctrl+W | Delete previous word |
| Ctrl+D | Delete char under cursor |
| Ctrl+B/F | Move backward/forward |
| Alt+B/F | Move word backward/forward |
| Ctrl+T | Transpose chars |

### 4.6 Key insight for Cozmo
- `@` fuzzy file search is a high-value UX win — implement with `fzf` or `prompt_toolkit` autocomplete.
- `!` shell passthrough is simple and powerful — just `subprocess.run()` with output fed to context.
- `/` commands are next logical step after basic readline.

---

## 5. Slash Commands

### 5.1 Built-in commands

| Command | Aliases | Action | Keybind |
|---------|---------|--------|---------|
| `/help` | — | Show help dialog | — |
| `/new` | `/clear` | Start new session | `Ctrl+X N` |
| `/exit` | `/quit`, `/q` | Exit | `Ctrl+X Q` |
| `/undo` | — | Undo last message + file changes | `Ctrl+X U` |
| `/redo` | — | Redo undone changes | `Ctrl+X R` |
| `/compact` | `/summarize` | Compact session context | `Ctrl+X C` |
| `/sessions` | `/resume`, `/continue` | List/switch sessions | `Ctrl+X L` |
| `/models` | — | List available models | `Ctrl+X M` |
| `/connect` | — | Add provider | — |
| `/init` | — | Create/update AGENTS.md | — |
| `/editor` | — | Open external editor | `Ctrl+X E` |
| `/export` | — | Export session to markdown | `Ctrl+X X` |
| `/share` | — | Share session | — |
| `/unshare` | — | Unshare session | — |
| `/details` | — | Toggle tool execution details | — |
| `/thinking` | — | Toggle reasoning block visibility | — |
| `/themes` | — | List themes | `Ctrl+X T` |

### 5.2 Custom commands (Markdown files)
```
.opencode/commands/test.md
---
description: Run tests with coverage  
agent: build  
model: anthropic/claude-3-5-sonnet-20241022  
---

Run the full test suite with coverage report and show any failures.
Focus on the failing tests and suggest fixes.
```

- File in `.opencode/commands/<name>.md` → `/name`
- Template supports:
  - `$ARGUMENTS` / `$1`, `$2` — positional params
  - `` !`shell command` `` — inline shell output injection
  - `@file` — file content injection

### 5.3 Key insight for Cozmo
- `/undo` and `/redo` require Git integration (stash snapshots before edits).
- `/compact` for context window management is critical for long sessions.
- Custom commands with `$ARGUMENTS` is a killer feature — `/test`, `/lint`, `/deploy` as repeatable prompts.
- `/init` for AGENTS.md generation is a great onboarding pattern.

---

## 6. Keyboard System

### 6.1 Leader key concept
- Default leader: `Ctrl+X`
- Two-stroke shortcuts: `Leader + key`
- Configurable via `tui.json`
- `leader_timeout: 2000` ms wait for second key
- Avoids conflicts with terminal emulators

### 6.2 Major keybinds (with leader)

| Action | Default |
|--------|---------|
| New session | `Ctrl+X N` |
| Session list | `Ctrl+X L` |
| Compact | `Ctrl+X C` |
| Undo | `Ctrl+X U` |
| Redo | `Ctrl+X R` |
| Open editor | `Ctrl+X E` |
| Export | `Ctrl+X X` |
| Help tips | `Ctrl+X H` |
| Status view | `Ctrl+X S` |
| Sidebar toggle | `Ctrl+X B` |
| Copy message | `Ctrl+X Y` |
| Models | `Ctrl+X M` |
| Themes | `Ctrl+X T` |
| Agent list | `Ctrl+X A` |

### 6.3 Non-leader keybinds

| Action | Default |
|--------|---------|
| Submit prompt | `Enter` |
| Newline | `Shift+Enter` |
| Interrupt response | `Escape` |
| Cycle agents | `Tab` / `Shift+Tab` |
| Cycle model variants | `Ctrl+T` |
| Cycle recent models | `F2` / `Shift+F2` |
| Command palette | `Ctrl+P` |
| Toggle sidebar | `Ctrl+B` |
| Page up/down | `PgUp` / `PgDn` |
| Copy on select | (default enabled) |

### 6.4 Key insight for Cozmo
- Leader key pattern is elegant for terminals — single reserved chord vs. dozens of conflicts.
- Cozmo could start with `Ctrl+X` as leader, map the 6-8 most common actions.
- `Tab` to cycle agents is the single most important UI pattern to replicate.

---

## 7. Permission System

### 7.1 Permission levels

| Level | Effect |
|-------|--------|
| `allow` | Run without approval |
| `ask` | Prompt user for approval |
| `deny` | Block the action |

### 7.2 Tools / permission keys

| Key | Tools gated | Granular? |
|-----|-------------|-----------|
| `read` | `read` | path patterns |
| `edit` | `write`, `edit`, `apply_patch` | path patterns |
| `glob` | `glob` | glob patterns |
| `grep` | `grep` | regex patterns |
| `bash` | `bash` | command patterns |
| `task` | `task` | subagent name patterns |
| `skill` | `skill` | skill name patterns |
| `webfetch` | `webfetch` | URL patterns |
| `websearch` | `websearch` | query patterns |
| `lsp` | `lsp` | (non-granular) |
| `question` | `question` | (non-granular) |
| `external_directory` | any tool touching outside CWD | path patterns |
| `doom_loop` | same tool call 3x identical input | (auto) |

### 7.3 Granular bash rules (object syntax)
```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "git commit *": "deny",
      "git push *": "deny",
      "rm *": "deny",
      "grep *": "allow",
      "npm *": "allow"
    }
  }
}
```
- Last matching pattern wins
- `*` wildcard, `?` single char

### 7.4 Permission prompt UX
- `once` — approve just this request
- `always` — approve matching pattern for session
- `deny` — block request
- Show shorthand pattern that would be whitelisted

### 7.5 Auto mode
- `opencode --auto` — auto-approve anything not explicitly denied
- Toggle in TUI via command palette
- Indicator in prompt: `auto` badge

### 7.6 Key insight for Cozmo
- Cozmo's current `run_command` gating is basic (Allow Once/Always/Deny). To level up:
  - Pattern-based whitelisting (e.g., `git *`, `npm *`) instead of exact command match.
  - Per-agent permission overrides (Plan = deny edit, Build = allow).
  - `--auto` flag for non-interactive mode.

---

## 8. Tool System

### 8.1 Built-in tools

| Tool | Function | Permission key |
|------|----------|----------------|
| `bash` | Execute shell commands | `bash` |
| `edit` | Search-and-replace text in files | `edit` |
| `write` | Create/overwrite files | `edit` |
| `read` | Read file contents | `read` |
| `grep` | Regex content search | `grep` |
| `glob` | File pattern matching | `glob` |
| `apply_patch` | Apply diff patches | `edit` |
| `skill` | Load SKILL.md | `skill` |
| `todowrite` | Manage task lists | `todowrite` |
| `webfetch` | Fetch URL content | `webfetch` |
| `websearch` | Web search (Exa) | `websearch` |
| `question` | Ask user questions | `question` |
| `lsp` | LSP code intelligence (experimental) | `lsp` |

### 8.2 Custom tools (JSON)
```json
{
  "tools": {
    "my-tool": {
      "description": "Does something useful",
      "command": "python scripts/do-thing.sh $args"
    }
  }
}
```

### 8.3 MCP servers
- Model Context Protocol for external tools
- `opencode mcp add` — guided setup
- `opencode mcp list` — show all with status
- OAuth support for remote MCP servers

### 8.4 Agent Skills (SKILL.md)
```
.opencode/skills/git-release/SKILL.md
---
name: git-release
description: Create consistent releases and changelogs
---
## What I do
- Draft release notes from merged PRs
- Propose a version bump
```

- Name must match: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Loaded on-demand via `skill` tool
- Discovered from `.opencode/skills/`, `.claude/skills/`, `~/.config/opencode/skills/`

### 8.5 Key insight for Cozmo
- Cozmo has tools grouped by function (calculator, file_ops, code_ops, etc.) — concept is same.
- Add `question` tool so model can ask user mid-task.
- Add `todowrite` tool for structured multi-step tracking.
- Skills via SKILL.md is a pattern Cozmo could adopt directly from PLAN.md's agent descriptions.

---

## 9. Rules & Configuration

### 9.1 AGENTS.md system
- **Project**: `AGENTS.md` in repo root (version-controlled, shared)
- **Global**: `~/.config/opencode/AGENTS.md` (personal, not shared)
- **Claude compat**: `CLAUDE.md` as fallback
- Precedence: local AGENTS.md > local CLAUDE.md > global AGENTS.md > global CLAUDE.md
- `/init` command generates AGENTS.md by scanning project

### 9.2 Instruction files
```json
{
  "instructions": [
    "CONTRIBUTING.md",
    "docs/guidelines.md",
    ".cursor/rules/*.md",
    "https://raw.githubusercontent.com/org/style.md"
  ]
}
```
- Globs supported
- Remote URLs supported (5s timeout)
- Combined with AGENTS.md content

### 9.3 Configuration files
- `opencode.json` / `opencode.jsonc` — runtime config
- `tui.json` / `tui.jsonc` — TUI-specific config (theme, keybinds, mouse, scroll, attention sounds)
- `OPENCODE_CONFIG` env var for custom path
- `OPENCODE_CONFIG_CONTENT` env var for inline JSON config

### 9.4 TUI config options
```json
{
  "theme": "tokyonight",
  "leader_timeout": 2000,
  "scroll_speed": 3,
  "scroll_acceleration": { "enabled": false },
  "diff_style": "auto",
  "mouse": true,
  "attention": {
    "enabled": true,
    "notifications": true,
    "sound": true,
    "volume": 0.4,
    "sound_pack": "opencode.default"
  },
  "keybinds": { "leader": "ctrl+x", "command_list": "ctrl+p" }
}
```

### 9.5 Key insight for Cozmo
- AGENTS.md pattern (project rules file) is a must-have. Cozmo already has `~/.cozmo/config.toml` for global config, could add `<project>/.cozmo/AGENTS.md` or similar.
- Separate TUI config from runtime config is a clean pattern.
- Attention sounds/notifications for async operations (like subagent completion).

---

## 10. Sessions & State

### 10.1 Session model
- Each conversation is a named session
- Sessions persisted to local database
- `Continue last session` flag (`--continue`)
- Resume specific session by ID (`--session`)
- Fork sessions for experimental branches
- Session titles auto-generated by Title agent

### 10.2 Context management
- Automatic compaction when context window fills (`/compact`)
- Compaction agent summarizes older messages
- `OPENCODE_DISABLE_AUTOCOMPACT` to disable
- Messages trimmed oldest-first

### 10.3 Undo/redo via Git
- `/undo` reverts last message + ALL file changes
- `/redo` restores them
- Requires Git repository
- Uses Git stash internally
- Only works if project is a Git repo

### 10.4 Session sharing
- `/share` generates shareable URL
- `/unshare` removes it
- `OPENCODE_AUTO_SHARE` env var
- `opencode import <url>` to load shared session

### 10.5 Key insight for Cozmo
- Git-based undo/redo for file changes is brilliant but requires Git CWD.
- ChromaDB already persists conversation history — sessions could be a simple list of past conversations.
- Auto-compaction based on token count.

---

## 11. Model & Provider System

### 11.1 Multi-provider
- 75+ providers (Anthropic, OpenAI, Google, AWS Bedrock, Groq, Azure, Ollama, OpenRouter)
- `opencode auth login` to configure API keys
- `opencode models` to list available
- `--model provider/model` syntax

### 11.2 Model variants
- `Ctrl+T` cycles through model variants (e.g., reasoning effort levels)
- Different temperature per model default
- Models.dev as provider registry

### 11.3 Key insight for Cozmo
- Cozmo already uses Ollama with specialist models (classifier → coder → etc.).
- The provider abstraction is less relevant for local-only, but the model-variant cycling (`Ctrl+T`) is interesting.
- Mapping: Cozmo's `--model` flag already exists.

---

## 12. Additional Features

### 12.1 GitHub integration
- `opencode github install` — sets up GitHub Actions workflow
- `/opencode` mention in issues → auto PRs
- Runs in GitHub Actions runner

### 12.2 IDE integration
- VS Code extension auto-installs when `opencode` runs in integrated terminal
- `Cmd+Esc` to toggle OpenCode split
- `@File#L37-42` syntax for line references
- Cursor, Windsurf, VSCodium support

### 12.3 LSP integration (experimental)
- Go to definition, find references, hover info
- `OPENCODE_EXPERIMENTAL_LSP_TOOL=true`
- Works with configured LSP servers

### 12.4 Plugins
- `opencode plugin <module>` — install from npm/PyPI
- Plugin ecosystem for extensions
- `OPENCODE_DISABLE_DEFAULT_PLUGINS` to disable built-ins

### 12.5 Theme system
- Built-in themes: tokyonight, everforest, ayu, catppuccin, gruvbox, kanagawa, nord, matrix, one-dark
- `system` theme adapts to terminal colors
- Custom themes via JSON with dark/light variants
- Theme directories: built-in → `~/.config/opencode/themes/` → `.opencode/themes/`

### 12.6 Notification system (Attention)
- Desktop notifications + sounds
- Configurable per event: error, question, permission, done, subagent_done
- Custom sound files
- Only when terminal is blurred (non-subagent)

---

## 13. Cozmo Feature Gap Analysis

### 13.1 Quick wins (Phase 4.5)
| Feature | Effort | Impact |
|---------|--------|--------|
| `@file` fuzzy autocomplete | Low | High (file awareness) |
| `!cmd` shell passthrough | Low | Medium (quick commands) |
| Status bar (model/tokens) | Low | Medium |
| `/help` command | Low | Medium |
| `/new` session | Low | Medium |

### 13.2 Medium effort (Phase 5)
| Feature | Effort | Impact |
|---------|--------|--------|
| Tab agent switching (Build ↔ Plan) | Medium | High |
| Agent config via markdown | Medium | High |
| Git-based undo/redo | Medium | High |
| Permission system with patterns | Medium | High |
| Custom slash commands | Medium | High |
| Configuration rewrite via CLI | Medium | Medium |

### 13.3 Major features (Phase 6+)
| Feature | Effort | Impact |
|---------|--------|--------|
| Rich TUI (textual/rich) | High | Very High |
| Context compaction | High | High |
| Leader key system | High | Medium |
| Session management UI | High | High |
| Subagent delegation (task tool) | High | Very High |
| Theme system | Medium | Medium |
| AGENTS.md rules | Medium | High |
| MCP server support | Very High | Medium |

### 13.4 Design principles to borrow
1. **One keystroke to switch roles** (Tab → Build/Plan)
2. **Progressively disclose complexity** (simple readline → rich TUI)
3. **Model knows what tools it has** (tool descriptions in system prompt)
4. **User controls permission at right granularity** (command pattern, not yes/no)
5. **Sessions are first-class** (resume, fork, share, export)
6. **Context is precious** (compact, summarize, trim automatically)
7. **Customization without code** (markdown agents, commands, skills, themes)
8. **Feedback loops** (attention sounds, desktop notifications, status indicators)

---

## 14. TUI Implementation for Cozmo (Python)

### 14.1 OpenCode/Claude Code TUI Architecture

OpenCode v0.0.55 used **Bubble Tea** (Go framework, Elm architecture). Later migrated to **OpenTUI** (Zig backend + TypeScript/React/Solid.js frontend bindings via C ABI). Claude Code uses proprietary TUI — details not public. Neither is directly usable from Python.

### 14.2 Python TUI Options Comparison

| Library | Type | Interactive | Styling | Best for | Windows 11 |
|---------|------|-------------|---------|----------|------------|
| **Textual** | Full app framework | Yes, async event loop | CSS-like `.tcss` | Full-screen TUIs, chat UIs | ✅ Full support |
| **Rich** | Rendering library | No (Live display only) | Markup + styles | Pretty output, progress bars | ✅ |
| **prompt-toolkit** | Input/REPL toolkit | Yes | Manual `FormattedTextControl` | Line editors, autocomplete | ✅ (already used) |
| **Urwid** | Widget toolkit | Yes, callback | Palette attributes | Mature apps, custom widgets | ⚠ Limited |
| **Blessed** | Terminal wrapper | You build it | Raw positioning | Low-level custom rendering | ✅ |

### 14.3 Recommended: Textual

**Why Textual wins for Cozmo:**
- Built on Rich (already in ecosystem) — 36k+ stars, very active
- CSS-based layout engine (flexbox, grid, dock) — familiar for web devs
- Full widget library: `Header`, `Footer`, `Input`, `RichLog`, `ScrollableContainer`, `Button`, `ListView`
- Async event loop — non-blocking tool execution with `run_worker()`
- Mouse support in Windows Terminal, Kitty, iTerm2, Alacritty
- Built-in theme system (dark/light, custom CSS variables)
- `textual-dev` tools: live reload, dev console, key/event inspector
- `App.sub_title` reactive attribute — live status updates
- Workers for long-running LLM calls without freezing UI

**Dependency footprint:** `textual` installs `rich` and `platformdirs` — no binary deps, pure Python.

### 14.4 Proposed Layout Architecture

```
┌──────────────────────────────────────────┐
│ Header                                    │
│  cozmo  │  ornith:9b  │  build  │  auto  │
├──────────────────────────────────────────┤
│                                          │
│  ChatLog (RichLog widget, scrollable)    │
│  ┌────────────────────────────────────┐  │
│  │ You: write a csv parser           │  │
│  │                                    │  │
│  │ Cozmo: Here's the code...         │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │ ▶ write_file results/csv…   │ │  │
│  │  │   (collapsed tool output)   │ │  │
│  │  └──────────────────────────────┘ │  │
│  │                                    │  │
│  │ [checkmark] Tool completed ✅     │  │
│  └────────────────────────────────────┘  │
│                                          │
├──────────────────────────────────────────┤
│  Input (Input widget)                     │
│  > @file.py !cmd /help                    │
├──────────────────────────────────────────┤
│  StatusBar                                │
│  turns:5  │  auto  │  F2:agent  │  ?help │
└──────────────────────────────────────────┘
```

### 14.5 Widget Breakdown

| Zone | Textual Widget | Behavior |
|------|---------------|----------|
| Header | `Header(show_clock=True)` | App name, model, agent name via `sub_title` reactive |
| Chat panel | `RichLog(highlight=True, markup=True)` | Append messages as `Text` or `Rich` objects; auto-scroll to bottom |
| Tool output | Collapsible `Vertical` inside `RichLog` | Expandable tool result blocks; toggle with click/keybind |
| Input | `Input(placeholder="Type a message...")` | `@` fuzzy file completer; `!` shell prefix detection; submit on Enter |
| Autocomplete | `Input` + custom completer | Same `FileCompleter` logic, adapted to Textual's completer API |
| Status bar | Custom `Static` widget | Polling or reactive: turn count, auto mode indicator, model name, agent name |
| Footer | `Footer()` | Keybind hints (automatically populated from app keybinds) |

### 14.6 Key Interactions

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│  Input       │─────▶│  App.on_submit() │─────▶│  Worker     │
│  (user text) │      │  - parse @ ! /   │      │  LLM call   │
└─────────────┘      │  - append to log  │      │  (async)    │
                     │  - run worker     │      └──────┬──────┘
                     └──────────────────┘             │
                                              ┌───────▼───────┐
                                              │  Worker       │
                                              │  callback     │
                                              │  - append     │
                                              │  response     │
                                              │  - exec tools │
                                              │  - update log │
                                              └───────────────┘
```

- **User submits** → `Input.submitted` message → `action_submit()` handler
- **Parse prefixes** → `@file` → attach file content, `!cmd` → shell passthrough, `/cmd` → slash command
- **Append to history** → `RichLog.write(Text(user_msg, style="bold blue"))`
- **Run LLM** → `self.run_worker(self._call_llm(user_input))` — non-blocking
- **Stream response** → worker yields tokens → `RichLog.write(token)` in real-time
- **Tool call detected** → `<tool>` JSON → permission check → execute → append result
- **Status updates** → reactive attribute `self.turn_count` auto-updates status bar

### 14.7 File Structure

```
cozmo/tui/
├── __init__.py
├── app.py              # ChatApp class (Textual App)
├── screens/
│   └── chat_screen.py  # Main chat screen
├── widgets/
│   ├── chat_log.py     # Custom ChatLog (extends RichLog)
│   ├── input_bar.py    # Custom InputBar with @ ! / parsing
│   ├── status_bar.py   # Status bar widget
│   └── tool_block.py   # Collapsible tool output
├── theme.tcss          # TCSS stylesheet
└── completer.py        # @file fuzzy completer (Textual adapter)
```

### 14.8 Migration Path

**Phase A — Textual wrapper around existing logic (now):**
- New `tui/app.py` — `ChatApp` class with `RichLog`, `Input`, status bar
- `coding_session()` in `cli.py` calls `app.run()` instead of prompt_toolkit loop
- Reuse `AgentRegistry`, `CodeAgent`, `PermissionResolver` unchanged
- Worker wraps `agent.run(user_input)` — blocks but shows "thinking..." indicator

**Phase B — Streaming (next):**
- Replace blocking `agent.run()` with token-by-token streaming
- `RichLog` updates in real-time as tokens arrive
- Tool calls appear inline with collapsible output

**Phase C — Full feature parity (future):**
- Tool output collapsing/expansion
- `/details` toggle for raw tool JSON
- `/thinking` toggle for reasoning blocks (model-dependent)
- Diff rendering (`auto` vs `stacked`)
- Theme configuration via `tui.json`

### 14.9 Key Design Decisions

1. **Textual not prompt_toolkit as TUI**: prompt_toolkit's `App` is a REPL builder, not a TUI framework. Textual provides proper layout, widgets, and rendering. Keep prompt_toolkit only if staying in simple mode (current `--auto` single-shot queries).
2. **Reuse existing agent code**: The TUI wraps existing `AgentRegistry`/`CodeAgent` — no logic migration. Only the user interface layer changes.
3. **Async worker pattern**: LLM calls run in `Worker` to keep UI responsive. Results stream back via `post_message()` or reactive updates.
4. **CSS-like styling**: TCSS files separate appearance from logic. Theme switching is a single file change.
5. **Single entry point**: `cozmo code` without `--auto` launches TUI. Same `cozmo code "query"` runs headless (current prompt_toolkit path). No breaking changes to existing CLI.

### 14.10 Prompt-toolkit TUI Alternative (lighter weight)

If Textual is too heavy, prompt_toolkit can build a basic split layout:

```python
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.widgets import TextArea, Label
from prompt_toolkit.layout.controls import FormattedTextControl

chat_area = TextArea(read_only=True, scrollbar=True)
input_field = TextArea(height=3, prompt="> ")
status_bar = Label(text="[model:ornith:9b turns:3]")

root = HSplit([
    Window(content=FormattedTextControl(chat_text), wrap_lines=True),
    Window(height=1, char="-"),
    input_field,
    Window(height=1, char="─"),
    status_bar,
])
layout = Layout(root)
```

**Limitations:** No mouse support, no styling, no proper widget tree, manual scroll management, poor resize handling. Fine for simple use but quickly hits walls.

### 14.11 Recommendation

**Use Textual.** It is the only Python TUI framework that:
1. Works properly on Windows 11
2. Provides scrollable chat history with markup
3. Supports mouse, keyboard, and resize events
4. Has a widget system rich enough for tool output blocks and status bars
5. Is actively maintained (36k stars, v6.5.0+ as of 2026)

Start with Phase A (Textual wrapper, blocking agent calls) and iterate toward Phase B (streaming) and Phase C (full features).

---

*End of reference — use for planning, not copying.*
