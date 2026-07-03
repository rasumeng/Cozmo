"""Shared test fixtures for Cozmo integration tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def mock_llm():
    """Mock OllamaModel that returns canned responses."""
    llm = MagicMock()

    def invoke_fn(messages=None, system_prompt=None):
        # Default: return a chat response
        return "Hello! I can help with that."

    llm.invoke = MagicMock(side_effect=invoke_fn)
    llm.stream = MagicMock(return_value=iter(["Hello", "!", " I", " can", " help."]))
    return llm


@pytest.fixture
def mock_llm_classifier():
    """Mock classifier that returns CHAT mode with no tools."""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value='{"mode": "CHAT", "use_tools": false, "tools": [], "reason": "simple chat"}')
    return llm


@pytest.fixture
def mock_llm_work_mode():
    """Mock classifier that returns WORK mode with tools."""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value='{"mode": "WORK", "use_tools": true, "tools": [{"name": "read_file", "args": {"path": "main.py"}}], "reason": "user wants to read file"}')
    return llm


@pytest.fixture
def mock_llm_research_mode():
    """Mock classifier that returns RESEARCH mode with search tools."""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value='{"mode": "RESEARCH", "use_tools": true, "tools": [{"name": "web_search", "args": {"query": "latest AI news"}}], "reason": "current events lookup"}')
    return llm


@pytest.fixture
def mock_memory():
    """Mock MemoryManager that returns filtered results."""
    memory = MagicMock()
    memory.query = MagicMock(return_value=[
        {"text": "User prefers dark mode", "distance": 0.3},
        {"text": "User asked about Python decorators", "distance": 0.4},
    ])
    return memory


@pytest.fixture
def mock_project_index():
    """Mock ProjectIndex that returns file snippets."""
    index = MagicMock()
    index.query = MagicMock(return_value="--- main.py ---\nprint('hello')")
    return index


@pytest.fixture
def mock_tools():
    """Mock tool registry with simple test tools."""
    tools = {}
    tools["calculator"] = lambda expression: str(eval(expression))
    tools["echo"] = lambda text: f"Echo: {text}"
    tools["read_file"] = lambda path: f"Content of {path}"
    tools["web_search"] = lambda query: f"Results for: {query}"
    return tools


@pytest.fixture
def sample_gate_chat():
    return {"mode": "CHAT", "use_tools": False, "tools": [], "reason": "chat"}


@pytest.fixture
def sample_gate_work():
    return {
        "mode": "WORK",
        "use_tools": True,
        "tools": [{"name": "read_file", "args": {"path": "test.py"}}],
        "reason": "read file",
    }


@pytest.fixture
def sample_gate_research():
    return {
        "mode": "RESEARCH",
        "use_tools": True,
        "tools": [{"name": "web_search", "args": {"query": "test"}}],
        "reason": "search",
    }
