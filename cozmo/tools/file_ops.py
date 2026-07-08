from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import register_tool

# Restrict reads to project root or subdirs
ALLOWED_ROOT = Path.cwd()
KNOWLEDGE = Path("./knowledge").resolve()


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


@register_tool()
def read_knowledge(path: str) -> str:
    """Read a file from the knowledge base.

    Args:
        path: Relative path inside knowledge base (e.g. 'learnings/python-patterns.md').
    """
    try:
        target = (KNOWLEDGE / path).resolve()
        try:
            target.relative_to(KNOWLEDGE)
        except ValueError:
            return "[error] Path traversal not allowed"
        if not target.exists():
            return f"[error] File not found: {path}"
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"[error] {e}"


@register_tool()
def write_knowledge(path: str, content: str, type: str = "Reference", title: str = "", tags: list[str] | None = None) -> str:
    """Write a file to the knowledge base with OKF frontmatter.

    Args:
        path: Relative path inside knowledge base (e.g. 'learnings/new-thing.md').
        content: The markdown body content.
        type: Concept type (Conversation, Learning, Project, Reference).
        title: Human-readable title.
        tags: List of tags for categorization.
    """
    try:
        target = (KNOWLEDGE / path).resolve()
        try:
            target.relative_to(KNOWLEDGE)
        except ValueError:
            return "[error] Path traversal not allowed"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        title = title or path.replace(".md", "").replace("/", " - ").replace("-", " ").title()
        tags = tags or []

        frontmatter = {
            "type": type,
            "title": title,
            "tags": tags,
            "timestamp": now,
        }

        with open(target, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, default_flow_style=False, allow_unicode=True)
            f.write("---\n\n")
            f.write(content)

        return f"[ok] Written to knowledge/{path}"
    except Exception as e:
        return f"[error] {e}"