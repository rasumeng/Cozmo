# Cozmo Audit & Improvement Plan

_Created: 2026-07-03. Senior Agent Engineer review. Unfiltered critique + prioritized fixes._

---

## Executive Summary

Cozmo has the bones of a competitive local AI agent. The agent harness (ReAct loop, permissions, tool system) exists and works. The TUI shell is clean. But the project suffers from **fragmented architecture**, **massive code duplication**, **dead code**, and **missing features** that competitors ship out of the box.

**Core problem**: Two parallel systems (CLI Orchestrator path vs TUI direct-agent path) that don't talk to each other. The Orchestrator's classification, memory, and routing are completely bypassed by the TUI.

---

## PART 1: BUGS (Things That Are Broken)

### B1. 'q' exits app from input fields
- **Files**: `tui/app.py:19`, `tui/screens/main.py:54`
- **Issue**: Both `CozmoApp.on_key` and `MainScreen.on_key` call `exit()` on 'q'. Pressing 'q' while typing in an input field kills the app.
- **Fix**: Check if input is focused before exiting. Or use `Ctrl+Q` instead.

### B2. Permission modal escape hang
- **File**: `tui/screens/permission.py:134`
- **Issue**: If user presses Escape (closes modal without clicking button), `threading.Event.wait()` hangs for 120s timeout. Agent thread frozen.
- **Fix**: Add `on_dismiss` handler that signals the event with `False`.

### B3. Typo in sidebar
- **File**: `tui/widgets/sidebar.py:37`
- **Issue**: `"Recent Sessoions:"` → `"Recent Sessions:"`

### B4. Model selector only works for ChatPanel
- **File**: `tui/screens/main.py:93-95`
- **Issue**: `on_model_selector_screen_model_selected` only calls `set_model` on ChatPanel. CollabPanel and CodePanel can't change models.
- **Fix**: Track which panel opened the selector, route selection to that panel.

### B5. ChatAgent has no history persistence
- **File**: `core/chat_agent.py`
- **Issue**: Each `run_stream()` call creates a fresh prompt. Agent forgets everything between messages.
- **Fix**: Add `self.history` list, inject into prompt, cap at N turns.

### B6. CollabAgent history grows unbounded
- **File**: `core/collab_agent.py:157-158`
- **Issue**: `self.history` list grows forever. No compaction or limit.
- **Fix**: Add max history limit + compaction.

### B7. load_chat doesn't restore agent history
- **File**: `tui/widgets/panels/panel.py` (ChatPanel.load_chat)
- **Issue**: Loading a saved chat shows messages visually but agent has no context of prior conversation.
- **Fix**: Rebuild agent history from loaded messages.

### B8. CodeInput ToggleMode never handled
- **File**: `tui/widgets/code_input.py:40-44`
- **Issue**: `ToggleMode` message is posted but no handler catches it. Build/Plan toggle does nothing.
- **Fix**: Either implement agent switching or remove the dead toggle.

### B9. compact() only on CodeAgent
- **File**: `cli.py:164`
- **Issue**: `/compact` calls `registry.current.compact()` but only CodeAgent has it. ChatAgent/CollabAgent crash.
- **Fix**: Add `compact()` to all agents.

### B10. _hide_thinking uses hardcoded ID across panels
- **File**: `tui/widgets/panels/panel.py`
- **Issue**: All panels use `#chat-thinking` as ID. Works because `query_one` scopes to subtree, but fragile.
- **Fix**: Use panel-specific IDs or use CSS classes instead.

---

## PART 2: DEAD CODE (Exists But Does Nothing)

| File | Line(s) | What | Why Dead |
|------|---------|------|----------|
| `core/agent.py` | 20-26 | `_tool_help()` | Never called |
| `core/agent.py` | 28-45 | `_run_tool()` | Only used in `Agent.run()` which TUI doesn't use |
| `core/agent.py` | 82-85 | `Agent.run_stream()` | Old version, TUI uses specialized agents |
| `core/orchestrator.py` | all | `Orchestrator` class | Only called from CLI `interactive_session()`, TUI bypasses it |
| `core/plan_agent.py` | all | `PlanAgent` | Not used in TUI, replaced by CollabAgent |
| `core/agent_registry.py` | all | `AgentRegistry` | Only used in CLI `coding_session()` |
| `telegram_bot.py` | all | Telegram bot | Not used in TUI |
| `tools/telegram.py` | all | Telegram tool | Not used in TUI |
| `tools/desktop.py` | all | Screenshot/clipboard | Gated by config, never used by TUI agents |
| `core/chat_agent.py` | 27-33 | `_tool_help()` | Duplicate, never called |
| `core/code_agent.py` | 81-113 | `run()` synchronous | TUI only uses `run_stream()` |

**Decision needed**: Keep CLI path alive, or remove dead code and consolidate on TUI?

---

## PART 3: CODE DUPLICATION (Maintenance Nightmare)

### D1. Tool call parsing (4 copies)
- `_parse_tool_call()` identical in: `agent.py`, `chat_agent.py`, `collab_agent.py`, `code_agent.py`
- **Fix**: Extract to `BaseAgent` or utility function.

### D2. Tool schema generation (4 copies)
- `_build_system()` / `_build_code_system()` duplicate tool schema logic across all agents.
- **Fix**: Single `_build_tool_schema(tools)` function.

### D3. Panel helpers (~250 lines duplicated)
- `_add_message`, `_show_thinking`, `_hide_thinking`, `_update_thinking`, `_clear_messages`, `_show_greeting`, `_hide_greeting`, `_update_stream_ui` copy-pasted across ChatPanel, CollabPanel, CodePanel.
- **Fix**: Extract into `ChatMixin` base class.

### D4. Streaming worker pattern (3 copies)
- `_stream_worker` + `on_worker_state_changed` duplicated across all panels.
- **Fix**: Generic streaming mixin or base class.

---

## PART 4: ARCHITECTURE ISSUES

### A1. Orchestrator bypassed in TUI
- **Current**: TUI creates agents directly, no classification, no memory.
- **Fix**: Wire Orchestrator into panels. Or: move classification/routing into panel level.

### A2. Memory disconnected
- **Current**: MemoryManager exists with ChromaDB, only used by dead Orchestrator path.
- **Fix**: Add memory injection to agent prompts. At minimum, short-term conversation memory.

### A3. No context window management
- **Current**: Agents accumulate history until they crash or produce garbage.
- **Fix**: Token counting + auto-compact. Steal CodeAgent's `compact()` for all agents.

### A4. Permission system dual-path
- **Current**: CLI uses `input()`, TUI uses modal via callback. Logic split across two places.
- **Fix**: Unify on callback pattern. CLI provides `input()`-based callback, TUI provides modal callback.

### A5. No error recovery
- **Current**: If Ollama fails mid-stream, agent dies. No retry, no graceful degradation.
- **Fix**: Retry with backoff, fallback to simpler model, user-facing error with retry option.

---

## PART 5: MISSING FEATURES (vs Competitors)

### Must-Have (Ship Blockers)
| Feature | Competitors | Cozmo Status |
|---------|-------------|--------------|
| Context compaction | Claude Code auto-compact | **Missing** |
| Markdown rendering | All | **Missing** — plain text only |
| @ file attachment | Claude Code, OpenCode | **CLI only** |
| Undo/redo | Claude Code | **Missing** |
| Keyboard shortcuts | All | **Missing** |

### Should-Have (Competitive Parity)
| Feature | Status |
|---------|--------|
| Syntax highlighting in responses | Missing |
| File diff view after edits | Missing |
| Search past conversations | Missing |
| Token/cost display | Missing |
| Retry on failure | Missing |
| Session persistence | Missing |
| Progress indicators (spinner) | Missing |

### Nice-to-Have (Differentiation)
| Feature | Status |
|---------|--------|
| Sub-agent spawning | Missing |
| Conversation branching | Missing |
| Multi-file atomic edits | Missing |
| Export chat history | Missing |
| Custom agent creation from TUI | Missing |

---

## PART 6: SECURITY ISSUES

### S1. eval() in calculator
- **File**: `tools/calculator.py:7`
- **Risk**: `eval(expression)` allows arbitrary code execution.
- **Fix**: Use `ast.literal_eval` or a safe math parser (e.g., `simpleeval` library).

### S2. Shell injection in run_command
- **File**: `tools/code_ops.py:44`
- **Risk**: `subprocess.run(command, shell=True)` with user input.
- **Fix**: Parse command, use `shell=False` with argument list. Or add whitelist.

### S3. Symlink path traversal
- **File**: `tools/file_ops.py:8-12`
- **Risk**: `_safe_path()` resolves but symlinks can escape project root.
- **Fix**: Resolve and verify real path, not just resolved path.

---

## PART 7: PERFORMANCE ISSUES

| Issue | File | Fix |
|-------|------|-----|
| OllamaModel not shared | All agents | Cache instances by model name |
| Tool schema regenerated every turn | All agents | Cache schema, rebuild only on tool change |
| ChromaDB queried every message | memory/manager.py | Skip query for short messages / greetings |
| Model list not cached | model_selector.py | Cache with TTL |
| History unbounded | collab_agent.py | Max history + compaction |

---

## PRIORITIZED IMPLEMENTATION PLAN

### Phase 1: Critical Fixes (1-2 hours)
_Things that are broken or security risks._

1. **Fix 'q' exit** — Check input focus before exiting
2. **Fix permission escape hang** — Signal event on modal dismiss
3. **Fix sidebar typo** — "Sessoions" → "Sessions"
4. **Fix eval() security** — Replace with safe math parser
5. **Fix shell injection** — Add command parsing/sanitization

### Phase 2: Architecture Cleanup (2-3 hours)
_Remove duplication, unify agent system._

6. **Extract BaseAgent** — Shared `_parse_tool_call`, `_build_tool_schema`, streaming loop
7. **Extract ChatMixin** — Panel helpers (_add_message, _show_thinking, etc.)
8. **Add history to ChatAgent** — Persist conversation between messages
9. **Add history limits to all agents** — Max turns + compaction
10. **Fix model selector routing** — Track which panel opened it

### Phase 3: Feature Parity (3-4 hours)
_Match competitor capabilities._

11. **Markdown rendering** — Rich markdown in agent responses
12. **@ file attachment in TUI** — File picker or @ mention
13. **Context compaction** — Auto-compact when approaching limit
14. **load_chat restores agent history** — Rebuild context from saved messages
15. **Wire Orchestrator into TUI** — Classification + memory for chat
16. **Add retry on failure** — Exponential backoff for Ollama calls

### Phase 4: UX Polish (2-3 hours)
_Things that make it feel professional._

17. **Keyboard shortcuts** — Ctrl+C cancel, Ctrl+L clear, Ctrl+Z undo
18. **Token/cost display** — Show in status bar
19. **Progress indicators** — Spinner during long operations
20. **Syntax highlighting** — Code blocks in responses
21. **File diff view** — Show what changed after edits
22. **Search past conversations** — Ctrl+F in sidebar

### Phase 5: Advanced (Future)
_Differentiation features._

23. Sub-agent spawning
24. Conversation branching
25. Multi-file atomic edits
26. Custom agent creation from TUI
27. Export chat history
28. Session auto-save/restore

---

## DECISIONS NEEDED

1. **Keep CLI path?** — The Orchestrator, AgentRegistry, and PlanAgent are only used in CLI. Remove them and consolidate on TUI? Or keep both paths alive?

2. **Agent inheritance model** — Current: `Agent` base, `CodeAgent(Agent)`, `PlanAgent(CodeAgent)`. Proposed: flat `BaseAgent` with composition. Which approach?

3. **Memory strategy** — Full ChromaDB (slow, persistent) or simple in-memory history (fast, ephemeral)? Or both with toggle?

4. **Tool system** — Current `<tool>` JSON blocks work but are fragile. Consider switching to Ollama's native tool calling API?

---

_Audit complete. Start with Phase 1._
