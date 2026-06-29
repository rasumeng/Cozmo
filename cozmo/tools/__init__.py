TOOL_REGISTRY = {}

def register_tool(name=None):
    def decorator(func):
        key = name or func.__name__
        TOOL_REGISTRY[key] = func
        return func
    return decorator

from . import calculator, file_ops, web_search, desktop, telegram
