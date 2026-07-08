import re
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from . import register_tool
from ddgs import DDGS


@register_tool()
def web_search(query: str, max_results: int = 5, timelimit: str = None) -> str:
    """Search the web for current information. Returns date-stamped results with title + snippet + URL.
    
    Args:
        query: Search query
        max_results: Number of results (default 5)
        timelimit: Time filter - 'd' (day), 'w' (week), 'm' (month), 'y' (year). Default: None (all time)
    """
    search_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        with DDGS() as ddgs:
            kwargs = {"query": query, "max_results": max_results}
            if timelimit:
                kwargs["timelimit"] = timelimit
            results = list(ddgs.text(**kwargs))
        if not results:
            return f"Search performed: {search_date}\nNo results found."
        lines = [f"Search performed: {search_date}"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**\n   {r['body']}\n   {r['href']}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching web: {e}"


@register_tool()
def fetch_url(url: str, max_length: int = 2000) -> str:
    """Fetch a URL and return clean text content.

    Args:
        url: The URL to fetch.
        max_length: Maximum characters to return (default 2000).
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > max_length:
            text = text[:max_length] + "\n[truncated]"

        return text
    except Exception as e:
        return f"[error] Failed to fetch URL: {e}"


@register_tool()
def web_fetch(url: str, max_length: int = 5000) -> str:
    """Fetch and read content from a URL. Returns cleaned article text using trafilatura."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                favor_precision=False,
                favor_recall=True,
            )
            if text and len(text) > 100:
                if len(text) > max_length:
                    text = text[:max_length] + "..."
                return text

        import urllib.request
        import re
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text or "No readable content found."
    except Exception as e:
        return f"Error fetching URL: {e}"
