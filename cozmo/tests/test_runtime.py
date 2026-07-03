"""Unit tests for CozmoRuntime — the native tool-calling agentic loop."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cozmo.core.runtime import CozmoRuntime


def _tool(x: str) -> str:
    """echo tool for tests."""
    return f"echo:{x}"


def _search(query: str) -> str:
    """fake search tool for tests."""
    return f"results-for:{query}"


def make_runtime(cfg=None, with_search=False):
    llm = MagicMock()
    tools = {"echo": _tool, "calculator": _tool}
    if with_search:
        tools["web_search_pipeline"] = _search
        tools["web_search"] = _search
    return CozmoRuntime(llm=llm, tools=tools, cfg=cfg or {}), llm


class FakeChunk(SimpleNamespace):
    """Stand-in for an AIMessageChunk with content + tool_calls."""
    def __init__(self, content="", tool_calls=None):
        super().__init__(content=content, tool_calls=tool_calls or [])


def bound_yielding(*chunks_per_step):
    """Fake bound runnable: each .stream call yields the next step's chunk(s)."""
    steps = iter(chunks_per_step)

    class _Bound:
        def stream(self, msgs):
            step = next(steps)
            if isinstance(step, (list, tuple)):
                yield from step
            else:
                yield step
    return _Bound()


# ── routing ───────────────────────────────────────────────────────────────────

class TestRoute:
    def test_route_work(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "work"
        assert rt._route("edit main.py") == "work"

    def test_route_falls_back_to_chat(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "banana"
        assert rt._route("hi") == "chat"

    def test_route_substring_match(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "This is research mode."
        assert rt._route("latest news") == "research"


# ── tool gating ────────────────────────────────────────────────────────────────

class TestToolGate:
    def test_chat_binds_no_tools(self):
        rt, _ = make_runtime()
        assert rt._tools_for_mode("chat") == []

    def test_work_binds_all_tools(self):
        rt, _ = make_runtime()
        names = {t.name for t in rt._tools_for_mode("work")}
        assert names == {"echo", "calculator"}

    def test_research_binds_subset(self):
        rt, _ = make_runtime(with_search=True)
        names = {t.name for t in rt._tools_for_mode("research")}
        assert "web_search" in names and "echo" not in names


# ── tool-call extraction ────────────────────────────────────────────────────────

class TestExtractCalls:
    def test_native_tool_calls(self):
        rt, _ = make_runtime()
        ai = FakeChunk(tool_calls=[{"name": "echo", "args": {"x": "1"}, "id": "a"}])
        assert rt._extract_calls(ai) == [{"name": "echo", "args": {"x": "1"}, "id": "a"}]

    def test_text_fallback_name_arguments(self):
        rt, _ = make_runtime()
        ai = FakeChunk(content='{"name": "echo", "arguments": {"x": "hi"}}')
        assert rt._extract_calls(ai) == [{"name": "echo", "args": {"x": "hi"}, "id": "echo"}]

    def test_text_fallback_ignores_unknown_tool(self):
        rt, _ = make_runtime()
        assert rt._extract_calls(FakeChunk(content='{"name": "nope", "arguments": {}}')) == []

    def test_plain_text_is_not_a_tool_call(self):
        rt, _ = make_runtime()
        assert rt._extract_calls(FakeChunk(content="just an answer")) == []


# ── permissions + execution ─────────────────────────────────────────────────────

class TestExec:
    def test_exec_unknown_tool_lists_available(self):
        rt, _ = make_runtime()
        out = rt._exec_tool("ghost", {})
        assert "unknown tool" in out and "echo" in out

    def test_exec_runs_allowed_tool(self):
        rt, _ = make_runtime()
        assert rt._exec_tool("echo", {"x": "hi"}) == "echo:hi"

    def test_ask_rule_defers_to_callback(self):
        rt, _ = make_runtime(cfg={"permissions": {"echo": "ask"}})
        rt.set_permission_callback(lambda name, args: False)
        assert "DENIED" in rt._exec_tool("echo", {"x": "hi"})

    def test_ask_rule_without_callback_denies(self):
        rt, _ = make_runtime(cfg={"permissions": {"echo": "ask"}})
        assert "DENIED" in rt._exec_tool("echo", {"x": "hi"})

    def test_deny_rule_blocks(self):
        rt, _ = make_runtime(cfg={"permissions": {"echo": "deny"}})
        rt.set_permission_callback(lambda name, args: True)  # callback must not matter
        assert "DENIED" in rt._exec_tool("echo", {"x": "hi"})

    def test_bad_args_reports_schema_hint(self):
        rt, _ = make_runtime()
        out = rt._exec_tool("echo", {"wrong": "arg"})
        assert "bad arguments" in out

    def test_sanitize_truncates(self):
        rt, _ = make_runtime(cfg={"runtime": {"max_tool_output_chars": 50}})
        out = rt._sanitize("A" * 500)
        assert "truncated" in out and len(out) < 200


# ── grounding search ────────────────────────────────────────────────────────────

class TestGrounding:
    def test_prefers_pipeline(self):
        rt, _ = make_runtime(with_search=True)
        assert rt._grounding_search("world cup") == "results-for:world cup"

    def test_no_search_tools_returns_empty(self):
        rt, _ = make_runtime(with_search=False)
        assert rt._grounding_search("q") == ""


# ── full loop (mocked llm) ────────────────────────────────────────────────────────

class TestLoop:
    def test_answers_without_tools(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "chat"
        llm.client.return_value = bound_yielding(FakeChunk(content="hello there"))
        tokens = [t for k, t in rt.run_stream("hi") if k == "token"]
        assert "".join(tokens) == "hello there"
        assert rt.history[-1] == ("hi", "hello there")

    def test_tool_then_answer(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "work"
        llm.bind_tools.return_value = bound_yielding(
            FakeChunk(tool_calls=[{"name": "echo", "args": {"x": "42"}, "id": "c1"}]),
            FakeChunk(content="the result is echo:42"),
        )
        events = list(rt.run_stream("run echo"))
        tokens = "".join(t for k, t in events if k == "token")
        assert tokens == "the result is echo:42"
        assert any("echo" in t for k, t in events if k == "thinking")

    def test_research_mode_runs_grounding_search(self):
        rt, llm = make_runtime(with_search=True)
        llm.invoke.return_value = "research"
        llm.bind_tools.return_value = bound_yielding(FakeChunk(content="grounded answer"))
        events = list(rt.run_stream("latest news"))
        assert any(t == "Searching..." for k, t in events if k == "thinking")
        assert "".join(t for k, t in events if k == "token") == "grounded answer"

    def test_step_limit_yields_message(self):
        rt, llm = make_runtime(cfg={"runtime": {"max_steps": 2}})
        llm.invoke.return_value = "work"
        # model calls a DIFFERENT tool every step, never answers
        llm.bind_tools.return_value = bound_yielding(
            FakeChunk(tool_calls=[{"name": "echo", "args": {"x": "1"}, "id": "a"}]),
            FakeChunk(tool_calls=[{"name": "echo", "args": {"x": "2"}, "id": "b"}]),
        )
        tokens = "".join(t for k, t in rt.run_stream("q") if k == "token")
        assert "ran out of steps" in tokens
        assert rt.history[-1][1] != ""  # never remember an empty answer

    def test_repeated_identical_call_gets_error_not_reexecution(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "work"
        call = {"name": "echo", "args": {"x": "same"}, "id": "a"}
        llm.bind_tools.return_value = bound_yielding(
            FakeChunk(tool_calls=[dict(call)]),
            FakeChunk(tool_calls=[dict(call)]),
            FakeChunk(content="fine, done"),
        )
        tokens = "".join(t for k, t in rt.run_stream("q") if k == "token")
        assert tokens == "fine, done"

    def test_suppresses_text_toolcall_json_from_stream(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "work"
        llm.bind_tools.return_value = bound_yielding(
            FakeChunk(content='{"name": "echo", "arguments": {"x": "9"}}'),
            FakeChunk(content="done, got echo:9"),
        )
        tokens = "".join(t for k, t in rt.run_stream("q") if k == "token")
        assert tokens == "done, got echo:9"

    def test_empty_model_output_yields_fallback(self):
        rt, llm = make_runtime()
        llm.invoke.return_value = "chat"
        llm.client.return_value = bound_yielding(FakeChunk(content=""))
        tokens = "".join(t for k, t in rt.run_stream("q") if k == "token")
        assert "no response" in tokens


# ── compaction + reset ───────────────────────────────────────────────────────────

class TestHistory:
    def test_compaction_summarizes_old_turns(self):
        rt, llm = make_runtime(cfg={"runtime": {"max_history": 4}})
        llm.invoke.return_value = "summary of old stuff"
        for i in range(6):
            rt._remember(f"q{i}", f"a{i}")
        assert len(rt.history) <= 4
        assert rt._summary == "summary of old stuff"

    def test_summary_lands_in_system_prompt(self):
        rt, _ = make_runtime()
        rt._summary = "user is building a TUI"
        assert "user is building a TUI" in rt._system_prompt("q", "chat")

    def test_date_in_system_prompt(self):
        rt, _ = make_runtime()
        import datetime
        assert str(datetime.date.today().year) in rt._system_prompt("q", "chat")

    def test_reset_clears_everything(self):
        rt, _ = make_runtime()
        rt.history.append(("a", "b"))
        rt._summary = "x"
        rt.reset()
        assert rt.history == [] and rt._summary == ""
