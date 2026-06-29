from . import register_tool
from ddgs import DDGS


@register_tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information. Returns title + snippet + URL."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"- {r['title']}: {r['body']} ({r['href']})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching web: {e}"
