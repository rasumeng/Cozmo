from dataclasses import dataclass
from typing import Callable
from langchain_core.tools import StructuredTool

@dataclass
class ToolInfo:
    name: str
    description: str
    fn: Callable

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(self, name: str, fn: Callable, description: str = "") -> None:
        self._tools[name] = ToolInfo(
            name=name,
            description=description or (fn.__doc__ or "").strip(),
            fn=fn,
        )

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def list(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def as_lc_tools(self) -> dict[str, StructuredTool]:
        wrapped: dict[str, StructuredTool] = {}
        for name, info in self._tools.items():
            try:
                wrapped[name] = StructuredTool.from_function(
                    func=info.fn, name=name, description=info.description.split("\n")[0],
                )
            except Exception:
                continue
        return wrapped
