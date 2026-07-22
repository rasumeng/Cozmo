# Changelog

## v0.2.0 (unreleased)

### UI Architecture
- Inline trace components: InlineTraceTimeline, InlineTraceStep, InlinePlanApproval
- Removed right-side panels: ActivityPanel, RightPanel, ActivityCard, StatusIndicator, TerminalPanel, DiffPanel, FileChangeCard
- Trace now renders inline between user/assistant messages
- Thinking bubble with pulsing dots persists across mode switches
- Conversation component shared via BaseConversation pattern across Chat/Agent/Code

### Streaming Pipeline
- Removed `{` suppression in runtime.py
- Reasoning token capture via reasoning=True on ChatOllama
- Chat handler yields (kind, text) tuples for unified event processing
- Reasoning and agent_status handlers in frontend WebSocket client
- Plan events properly wired through webui_server.py

### Settings & Configuration
- ModelManager.reload_models() — hot-reload models from config without restart
- ModelManager.set_lightweight_mode() — toggle lightweight mode at runtime
- Fixed deep_merge in webui_server.py preserving models dict on config update
- SettingsModal.save() now persists agent, mcp, personality, memory sections
- Fixed AgentSettings duplicate model source (uses Models tab read-only)
- Fixed ModelSelect width (w-48 → min-w-[180px])
- Fixed CSS typo in ConnectorsSection (border-accept/40 → border-accent/40)
- Expanded SettingsData type with RuntimeConfig, AgentConfig, McpServerConfig

### Agent Events (WebSocket)
- Tool category mapping: workspace/python/web/git/memory/other in tool_call events
- Structured plan steps alongside free-text plan for rich plan display
- Progress event (current, total, label) during agent step execution
- Agent state event (current_goal, status, tools_used) at lifecycle transitions
- All new events wired through webui_server.py → frontend ServerEvent type

### Frontend Types & Hooks
- Added AgentStateInfo, ProgressInfo, PlanStepInfo types
- Updated ServerEvent union with progress, agent_state, tool_call.category, plan.steps
- useCozmoChat exposes agentState and progress state
- Handlers for all new event types

## v0.1.0 (unreleased)

- Initial public release
- CLI agent with specialist model routing (chat, coder, vision, research)
- ChromaDB-backed memory with auto-summarization
- Tool system: calculator, file I/O, web search, code ops, git, desktop, Telegram
- WebUI (React/TypeScript) with streaming, permissions, settings
- Search pipeline with query rewrite, multi-source, content extraction, synthesis
- MCP server protocol support
- Permission system with pattern-based gating (allow/ask/deny)
- Code project index for codebase-aware queries
