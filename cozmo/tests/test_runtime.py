"""Integration tests for CozmoRuntime — the core pipeline."""

import json
import re
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from cozmo.core.runtime import CozmoRuntime, _COMPILE_STRIP_PATTERNS


# ══════════════════════════════════════════════════════════════════════════════
# compile() — Response Compiler
# ══════════════════════════════════════════════════════════════════════════════

class TestCompile:
    """Test the response compiler strips all tool artifacts."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_strips_tool_block(self):
        draft = "Here is the answer.<tool>{\"tool\": \"web_search\", \"args\": {\"query\": \"test\"}}</tool>Done."
        result = self.runtime.compile(draft)
        assert "<tool>" not in result
        assert "</tool>" not in result
        assert "Here is the answer." in result
        assert "Done." in result

    def test_strips_opening_tool_tag(self):
        draft = "Answer before <tool>{\"tool\": \"x\"} after"
        result = self.runtime.compile(draft)
        assert "<tool>" not in result
        assert "Answer before" in result
        assert "after" in result

    def test_strips_closing_tool_tag(self):
        draft = "Answer </tool> after"
        result = self.runtime.compile(draft)
        assert "</tool>" not in result
        assert "Answer" in result
        assert "after" in result

    def test_strips_web_search_block(self):
        draft = "Result:<web_search>{\"query\": \"test\"}</web_search>Done."
        result = self.runtime.compile(draft)
        assert "<web_search>" not in result
        assert "</web_search>" not in result
        assert "Result:" in result
        assert "Done." in result

    def test_strips_web_fetch_block(self):
        draft = "Result:<web_fetch>{\"url\": \"http://x\"}</web_fetch>Done."
        result = self.runtime.compile(draft)
        assert "<web_fetch>" not in result
        assert "</web_fetch>" not in result
        assert "Done." in result

    def test_strips_multiple_tool_blocks(self):
        draft = "A<tool>1</tool>B<tool>2</tool>C"
        result = self.runtime.compile(draft)
        assert "<tool>" not in result
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_removes_cozmo_prefix(self):
        draft = "Cozmo: Cozmo: Hello!"
        result = self.runtime.compile(draft)
        assert result.startswith("Hello!")
        assert "Cozmo:" not in result

    def test_normalizes_whitespace(self):
        draft = "Line1\n\n\n\n\nLine2"
        result = self.runtime.compile(draft)
        assert "\n\n\n" not in result
        assert "Line1" in result
        assert "Line2" in result

    def test_strips_nested_tool_tags(self):
        draft = "Before <tool><web_search>{\"q\": \"x\"}</web_search></tool> After"
        result = self.runtime.compile(draft)
        assert "<tool>" not in result
        assert "<web_search>" not in result
        assert "Before" in result
        assert "After" in result

    def test_clean_text_unchanged(self):
        draft = "This is a perfectly normal response with no tool calls."
        result = self.runtime.compile(draft)
        assert result == draft

    def test_empty_string(self):
        result = self.runtime.compile("")
        assert result == ""

    def test_only_tool_blocks_stripped(self):
        draft = "<tool>{\"tool\": \"x\"}</tool>"
        result = self.runtime.compile(draft)
        assert result == ""


# ══════════════════════════════════════════════════════════════════════════════
# _sanitize_output() — Tool Output Sanitizer
# ══════════════════════════════════════════════════════════════════════════════

class TestSanitizeOutput:
    """Test tool output sanitization (capping + XML removal)."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_short_output_unchanged(self):
        text = "Short tool output"
        result = self.runtime._sanitize_output(text)
        assert result == text

    def test_long_output_capped(self):
        text = "A" * 20000
        result = self.runtime._sanitize_output(text)
        assert len(result) < 20000
        assert "truncated" in result

    def test_strips_xml_from_output(self):
        text = "Result: <tool>secret</tool> done"
        result = self.runtime._sanitize_output(text)
        assert "<tool>" not in result
        assert "Result:" in result
        assert "done" in result

    def test_strips_web_search_from_output(self):
        text = "Found: <web_search>query</web_search> results"
        result = self.runtime._sanitize_output(text)
        assert "<web_search>" not in result
        assert "Found:" in result

    def test_capping_preserves_head_and_tail(self):
        text = "HEAD" + "X" * 20000 + "TAIL"
        result = self.runtime._sanitize_output(text)
        assert "HEAD" in result[:100]
        assert "TAIL" in result[-100:]


# ══════════════════════════════════════════════════════════════════════════════
# _parse_gate() — Gate Response Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestParseGate:
    """Test classify+tool_gate response parsing."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_parse_valid_chat_gate(self):
        raw = '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}'
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "CHAT"
        assert result["use_tools"] is False
        assert result["tools"] == []

    def test_parse_valid_work_gate(self):
        raw = '{"mode": "WORK", "use_tools": true, "tools": [{"name": "read_file", "args": {"path": "x.py"}}], "reason": "file read"}'
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "WORK"
        assert result["use_tools"] is True
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "read_file"

    def test_parse_valid_research_gate(self):
        raw = '{"mode": "RESEARCH", "use_tools": true, "tools": [{"name": "web_search", "args": {"query": "test"}}], "reason": "search"}'
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "RESEARCH"

    def test_parse_invalid_mode_falls_back_to_chat(self):
        raw = '{"mode": "INVALID", "use_tools": false, "tools": [], "reason": "bad"}'
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "CHAT"

    def test_parse_invalid_json_falls_back(self):
        raw = "This is not JSON at all"
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "CHAT"
        assert result["use_tools"] is False

    def test_parse_empty_string_falls_back(self):
        result = self.runtime._parse_gate("")
        assert result["mode"] == "CHAT"

    def test_parse_none_falls_back(self):
        result = self.runtime._parse_gate(None)
        assert result["mode"] == "CHAT"

    def test_parse_wraps_in_markdown_fences(self):
        raw = '```json\n{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "test"}\n```'
        result = self.runtime._parse_gate(raw)
        assert result["mode"] == "CHAT"

    def test_parse_limits_tool_calls(self):
        tools = [{"name": f"tool_{i}", "args": {}} for i in range(10)]
        raw = json.dumps({"mode": "WORK", "use_tools": True, "tools": tools, "reason": "many tools"})
        result = self.runtime._parse_gate(raw)
        assert len(result["tools"]) <= self.runtime.max_tool_calls

    def test_parse_tools_not_list_falls_back(self):
        raw = '{"mode": "WORK", "use_tools": true, "tools": "not_a_list", "reason": "bad"}'
        result = self.runtime._parse_gate(raw)
        assert result["tools"] == []


# ══════════════════════════════════════════════════════════════════════════════
# execute_tools() — Tool Execution Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestExecuteTools:
    """Test tool execution with sanitization."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_no_tools_returns_empty(self):
        gate = {"use_tools": False, "tools": []}
        result = self.runtime.execute_tools(gate)
        assert result == []

    def test_executes_single_tool(self):
        tools = {"echo": lambda text: f"Echo: {text}"}
        self.runtime.tools = tools
        gate = {"use_tools": True, "tools": [{"name": "echo", "args": {"text": "hello"}}]}
        result = self.runtime.execute_tools(gate)
        assert len(result) == 1
        assert result[0]["tool"] == "echo"
        assert "Echo: hello" in result[0]["output"]

    def test_unknown_tool_returns_error(self):
        gate = {"use_tools": True, "tools": [{"name": "nonexistent", "args": {}}]}
        result = self.runtime.execute_tools(gate)
        assert len(result) == 1
        assert "Error" in result[0]["output"]

    def test_tool_exception_returns_error(self):
        def bad_tool():
            raise ValueError("boom")
        self.runtime.tools = {"bad": bad_tool}
        gate = {"use_tools": True, "tools": [{"name": "bad", "args": {}}]}
        result = self.runtime.execute_tools(gate)
        assert "Error" in result[0]["output"]

    def test_sanitizes_tool_output(self):
        def xml_tool(text):
            return f"Result: <tool>{text}</tool>"
        self.runtime.tools = {"xml": xml_tool}
        gate = {"use_tools": True, "tools": [{"name": "xml", "args": {"text": "secret"}}]}
        result = self.runtime.execute_tools(gate)
        assert "<tool>" not in result[0]["output"]
        assert "Result:" in result[0]["output"]

    def test_respects_max_tool_calls(self):
        self.runtime.tools = {"t": lambda: "ok"}
        tools = [{"name": "t", "args": {}} for i in range(10)]
        gate = {"use_tools": True, "tools": tools}
        result = self.runtime.execute_tools(gate)
        assert len(result) <= self.runtime.max_tool_calls


# ══════════════════════════════════════════════════════════════════════════════
# build_context() — Context Builder
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildContext:
    """Test context building with memory and project filtering."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_returns_all_keys(self):
        ctx = self.runtime.build_context("hello")
        assert "history" in ctx
        assert "memory" in ctx
        assert "project" in ctx

    def test_empty_history_returns_no_prior(self):
        ctx = self.runtime.build_context("hello")
        assert "no previous conversation" in ctx["history"]

    def test_history_accumulates(self):
        self.runtime.history = [("hi", "hello"), ("how are you", "fine")]
        ctx = self.runtime.build_context("what's next")
        assert "hi" in ctx["history"]
        assert "how are you" in ctx["history"]

    def test_history_trimmed(self):
        self.runtime.history = [(f"u{i}", f"a{i}") for i in range(20)]
        ctx = self.runtime.build_context("test")
        assert "u0" not in ctx["history"]
        assert "u19" in ctx["history"]

    def test_memory_with_no_manager(self):
        self.runtime.memory = None
        ctx = self.runtime.build_context("test")
        assert "no memories" in ctx["memory"]

    def test_project_with_no_index(self):
        self.runtime.project_index = None
        ctx = self.runtime.build_context("test")
        assert "no project context" in ctx["project"]


# ══════════════════════════════════════════════════════════════════════════════
# run() — Full Pipeline End-to-End
# ══════════════════════════════════════════════════════════════════════════════

class TestRunPipeline:
    """Test the full run() pipeline with mocked components."""

    def setup_method(self):
        self.llm = MagicMock()
        self.runtime = CozmoRuntime(llm=self.llm)

    def test_chat_mode_no_tools(self):
        """CHAT mode: classify → no tools → generate → compile."""
        responses = [
            '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}',  # classify
            "Hello! How can I help you today?",  # generate
        ]
        self.llm.invoke = MagicMock(side_effect=responses)

        result = self.runtime.run("hello")
        assert "Hello!" in result
        assert "<tool>" not in result

    def test_work_mode_with_tools(self):
        """WORK mode: classify → tool → generate → compile."""
        responses = [
            '{"mode": "WORK", "use_tools": true, "tools": [{"name": "echo", "args": {"text": "test"}}], "reason": "test"}',  # classify
            "The file contains test content.",  # generate
        ]
        self.llm.invoke = MagicMock(side_effect=responses)
        self.runtime.tools = {"echo": lambda text: f"Echo: {text}"}

        result = self.runtime.run("read the file")
        assert "file contains" in result
        assert "<tool>" not in result

    def test_response_has_no_tool_xml(self):
        """Even if LLM generates tool XML in response, compile() strips it."""
        responses = [
            '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}',
            'Here is the answer.<tool>{"tool": "x"}</tool>Done.',
        ]
        self.llm.invoke = MagicMock(side_effect=responses)

        result = self.runtime.run("test")
        assert "<tool>" not in result
        assert "Here is the answer." in result
        assert "Done." in result

    def test_history_grows(self):
        """Each run adds to history."""
        responses = [
            '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}',
            "Response 1",
            '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}',
            "Response 2",
        ]
        self.llm.invoke = MagicMock(side_effect=responses)

        self.runtime.run("msg1")
        self.runtime.run("msg2")
        assert len(self.runtime.history) == 2

    def test_history_trimmed_on_overflow(self):
        """History stays within max_history limit."""
        self.runtime.max_history = 3
        for i in range(10):
            responses = [
                '{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}',
                f"Response {i}",
            ]
            self.llm.invoke = MagicMock(side_effect=responses)
            self.runtime.run(f"msg{i}")

        assert len(self.runtime.history) <= 3

    def test_error_handling(self):
        """Pipeline handles LLM errors gracefully."""
        self.llm.invoke = MagicMock(side_effect=Exception("LLM down"))
        result = self.runtime.run("test")
        assert "error" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# run_stream() — Hybrid Streaming
# ══════════════════════════════════════════════════════════════════════════════

class TestRunStream:
    """Test hybrid streaming yields clean tokens."""

    def setup_method(self):
        self.llm = MagicMock()
        self.runtime = CozmoRuntime(llm=self.llm)

    def test_stream_yields_status(self):
        """Stream starts with status/thinking messages."""
        self.llm.invoke = MagicMock(
            return_value='{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}'
        )
        self.llm.stream = MagicMock(return_value=iter(["Hello", " world"]))

        events = list(self.runtime.run_stream("hi"))
        kinds = [e[0] for e in events]
        assert "status" in kinds or "thinking" in kinds

    def test_stream_yields_tokens(self):
        """Stream yields token events."""
        self.llm.invoke = MagicMock(
            return_value='{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}'
        )
        self.llm.stream = MagicMock(return_value=iter(["Hello", " world"]))

        events = list(self.runtime.run_stream("hi"))
        token_events = [e for e in events if e[0] == "token"]
        assert len(token_events) > 0

    def test_stream_no_tool_xml_leaks(self):
        """Stream filters out tool blocks from tokens."""
        self.llm.invoke = MagicMock(
            return_value='{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "chat"}'
        )
        # Simulate tokens with tool XML
        self.llm.stream = MagicMock(return_value=iter([
            "Here is ",
            "<tool>{\"tool\": \"x\"}",
            "</tool>",
            " the answer."
        ]))

        events = list(self.runtime.run_stream("test"))
        token_texts = "".join(e[1] for e in events if e[0] == "token")
        assert "<tool>" not in token_texts
        assert "</tool>" not in token_texts

    def test_stream_with_tool_execution(self):
        """Stream handles WORK mode with tool calls."""
        self.llm.invoke = MagicMock(
            return_value='{"mode": "WORK", "use_tools": true, "tools": [{"name": "echo", "args": {"text": "hi"}}], "reason": "test"}'
        )
        self.runtime.tools = {"echo": lambda text: f"Echo: {text}"}
        self.llm.stream = MagicMock(return_value=iter(["Tool result processed."]))

        events = list(self.runtime.run_stream("do something"))
        token_texts = "".join(e[1] for e in events if e[0] == "token")
        assert "<tool>" not in token_texts


# ══════════════════════════════════════════════════════════════════════════════
# Memory Filtering Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestMemoryFiltering:
    """Test that memory is filtered by distance threshold."""

    def setup_method(self):
        self.runtime = CozmoRuntime(llm=MagicMock())

    def test_filters_high_distance_memories(self):
        memory = MagicMock()
        memory.query = MagicMock(return_value=[
            {"text": "relevant", "distance": 0.2},
            {"text": "somewhat relevant", "distance": 0.4},
            {"text": "irrelevant", "distance": 0.8},
        ])
        self.runtime.memory = memory

        result = self.runtime._query_memory("test")
        assert "relevant" in result
        assert "somewhat relevant" in result
        assert "irrelevant" not in result

    def test_all_filtered_returns_no_relevant(self):
        memory = MagicMock()
        memory.query = MagicMock(return_value=[
            {"text": "far away", "distance": 0.9},
        ])
        self.runtime.memory = memory

        result = self.runtime._query_memory("test")
        assert "no relevant memories" in result

    def test_respects_max_memory_results(self):
        memory = MagicMock()
        memory.query = MagicMock(return_value=[
            {"text": f"memory {i}", "distance": 0.1} for i in range(10)
        ])
        self.runtime.memory = memory
        self.runtime.max_memory_results = 2

        result = self.runtime._query_memory("test")
        # Should only contain 2 memory lines
        lines = [l for l in result.split("\n") if l.startswith("- ")]
        assert len(lines) <= 2


# ══════════════════════════════════════════════════════════════════════════════
# Tool Output Capping Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestToolOutputCapping:
    """Test that tool outputs are properly capped."""

    def test_read_file_capped(self):
        from cozmo.tools.file_ops import read_file
        import os

        test_dir = os.path.join(os.getcwd(), ".test_tmp")
        os.makedirs(test_dir, exist_ok=True)
        path = os.path.join(test_dir, "big_file.txt")

        try:
            with open(path, "w") as f:
                f.write("A" * 10000)
            result = read_file(path)
            assert len(result) < 10000
            assert "truncated" in result
        finally:
            os.unlink(path)
            os.rmdir(test_dir)

    def test_run_command_capped(self):
        from cozmo.tools.code_ops import run_command
        result = run_command("python -c \"print('A' * 10000)\"")
        # Should be capped, not full 10000 chars
        assert "truncated" in result or len(result) < 10000
