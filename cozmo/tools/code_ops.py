import subprocess
import re
from pathlib import Path
from . import register_tool

@register_tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with content."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {path}"

@register_tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace exact text in an existing file (first occurrence)."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    if old_text not in content:
        return f"Error: text not found in {path}"
    p.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"Replaced match in {path}"

@register_tool()
def grep_search(pattern: str, path: str = ".") -> str:
    """Regex search across files (Python fallback)."""
    root = Path(path)
    results = []
    for f in root.rglob("*"):
        if not f.is_file() or ".git" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line):
                    results.append(f"{f}:{i}: {line.strip()}")
        except Exception:
            pass
    return "\n".join(results[:200]) or "No matches found."

@register_tool()
def run_command(command: str) -> str:
    """Execute a shell command safely. Pipes and redirects allowed."""
    import shlex
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()

    blocked = {"rm", "del", "format", "shutdown", "reboot", "mkfs", "dd"}
    if parts and parts[0].lower() in blocked:
        return f"Error: command '{parts[0]}' is blocked for safety"

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = result.stdout
        if result.stderr:
            out += f"\nSTDERR:\n{result.stderr}"
        if len(out) > 10000:
            head = out[:2000]
            tail = out[-8000:]
            out = f"{head}\n... [{len(out) - 10000} chars truncated] ...\n{tail}"
        return out or "(no output)"
    except Exception as e:
        return f"Error: {e}"

@register_tool()
def git_diff() -> str:
    """Show unstaged git diff."""
    result = subprocess.run(["git", "diff"], capture_output=True, text=True, timeout=30)
    out = result.stdout or "(no unstaged changes)"
    if len(out) > 10000:
        head = out[:2000]
        tail = out[-8000:]
        out = f"{head}\n... [{len(out) - 10000} chars truncated] ...\n{tail}"
    return out


@register_tool()
def git_log(lines: int = 10) -> str:
    """Show recent commit history."""
    result = subprocess.run(["git", "log", f"-{lines}", "--oneline"], capture_output=True, text=True, timeout=30)
    return result.stdout or "(no commits)"