"""Quick verification tests for CozmoBrain integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_tool_registry():
    from cozmo.tools import TOOL_REGISTRY
    required = {
        "execute_python", "fetch_url", "web_search",
        "read_knowledge", "write_knowledge", "web_fetch",
        "calculator", "read_file", "write_file", "git_diff",
        "git_log", "run_command", "edit_file", "grep_search",
        "list_directory", "web_search_pipeline",
    }
    registered = set(TOOL_REGISTRY.keys())
    missing = required - registered
    assert not missing, f"Missing tools: {missing}"
    print(f"TOOL_REGISTRY: {len(registered)} tools OK")


def test_core_imports():
    from cozmo.core import (
        MCPHost, ToolRouter, StatelessLLM,
        trim_history, truncate_tool_responses,
        compact_messages, estimate_tokens,
        build_system_prompt,
    )
    assert MCPHost
    assert ToolRouter
    assert StatelessLLM
    print("Core imports OK")


def test_tool_router_classify():
    from cozmo.core import ToolRouter
    router = ToolRouter(use_llm=False)
    result = router.classify("show me the git status")
    assert result is not None
    tools = router.get_tools("show git status", [lambda: None])
    assert isinstance(tools, list)
    print(f"ToolRouter classify 'git status': {result}")
    print(f"ToolRouter get_tools: {len(tools)} tools")


def test_tool_router_no_match():
    from cozmo.core import ToolRouter
    router = ToolRouter(use_llm=False)
    result = router.classify("asdfghjkl")
    assert result is None
    print("ToolRouter no-match returns None OK")


def test_build_system_prompt():
    from cozmo.core import build_system_prompt
    def fake_tool():
        pass
    prompt = build_system_prompt([fake_tool], workspace="/workspace", git_repo="/repo")
    assert "fake_tool" in prompt
    assert "/workspace" in prompt
    assert "/repo" in prompt
    assert "Today is" in prompt
    print("build_system_prompt OK")


def test_trim_history():
    from cozmo.core import trim_history
    msgs = list(range(30))
    trimmed = trim_history(msgs, max_messages=10)
    assert len(trimmed) == 10
    assert trimmed[0] == 0
    print("trim_history OK")


def test_estimate_tokens():
    from cozmo.core import estimate_tokens
    assert estimate_tokens("hello world") == 2
    print("estimate_tokens OK")


def test_truncate_tool_response():
    from cozmo.core import truncate_tool_response
    assert truncate_tool_response("short") == "short"
    long = "x" * 5000
    truncated = truncate_tool_response(long, max_chars=100)
    assert len(truncated) < len(long)
    assert "[truncated]" in truncated
    print("truncate_tool_response OK")


def test_stateless_llm_instantiate():
    from cozmo.core import StatelessLLM
    llm = StatelessLLM("dummy:latest")
    assert llm.model_name == "dummy:latest"
    print("StatelessLLM instantiate OK")


def test_config_defaults():
    from cozmo.config import DEFAULT_CONFIG
    assert "router" in DEFAULT_CONFIG
    assert "workspace" in DEFAULT_CONFIG
    assert "search" in DEFAULT_CONFIG
    assert "mcp" in DEFAULT_CONFIG
    assert "context" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["router"]["use_llm"] is False
    assert DEFAULT_CONFIG["workspace"]["path"] == "./workspace"
    print("Config defaults OK")


def test_mcp_host_instantiate():
    from cozmo.core import MCPHost
    host = MCPHost({"servers": {}})
    assert host.config == {"servers": {}}
    print("MCPHost instantiate OK")


def test_execute_python():
    from cozmo.tools import TOOL_REGISTRY
    fn = TOOL_REGISTRY["execute_python"]
    result = fn("print('hello from brain')")
    assert "hello from brain" in result
    print("execute_python OK")


def test_read_knowledge_missing():
    from cozmo.tools import TOOL_REGISTRY
    fn = TOOL_REGISTRY["read_knowledge"]
    result = fn("/nonexistent")
    assert "error" in result.lower() or "not found" in result.lower()
    print("read_knowledge missing file OK")


def test_fetch_url():
    from cozmo.tools import TOOL_REGISTRY
    fn = TOOL_REGISTRY["fetch_url"]
    result = fn("http://example.com", max_length=100)
    assert "Example Domain" in result or "example" in result.lower() or "[error]" in result
    print(f"fetch_url OK (got {len(result)} chars)")


if __name__ == "__main__":
    tests = [
        test_core_imports,
        test_tool_registry,
        test_tool_router_classify,
        test_tool_router_no_match,
        test_build_system_prompt,
        test_trim_history,
        test_estimate_tokens,
        test_truncate_tool_response,
        test_stateless_llm_instantiate,
        test_config_defaults,
        test_mcp_host_instantiate,
        test_execute_python,
        test_read_knowledge_missing,
        test_fetch_url,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
