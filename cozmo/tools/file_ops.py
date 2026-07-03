from pathlib import Path
from . import register_tool

# Restrict reads to project root or subdirs
ALLOWED_ROOT = Path.cwd()


def _safe_path(path: str) -> Path | None:
    resolved = (ALLOWED_ROOT / path).resolve()
    if ALLOWED_ROOT in resolved.parents or resolved == ALLOWED_ROOT:
        return resolved
    return None


@register_tool()
def read_file(path: str) -> str:
    """Read contents of a text file (capped at 5000 chars)."""
    safe = _safe_path(path)
    if safe is None:
        return "Error: path outside allowed directory"
    if not safe.exists():
        return "Error: file not found"
    if not safe.is_file():
        return "Error: not a file"
    try:
        text = safe.read_text(encoding="utf-8")
        if len(text) > 5000:
            return text[:5000] + f"\n... [truncated, {len(text)} total chars]"
        return text
    except Exception as e:
        return f"Error reading file: {e}"


@register_tool()
def list_directory(path: str = ".") -> str:
    """List files and directories at the given path."""
    safe = _safe_path(path)
    if safe is None:
        return "Error: path outside allowed directory"
    if not safe.exists():
        return "Error: path not found"
    if not safe.is_dir():
        return "Error: not a directory"
    try:
        entries = [str(e.name) + ("/" if e.is_dir() else "") for e in safe.iterdir()]
        return "\n".join(sorted(entries))
    except Exception as e:
        return f"Error listing directory: {e}"