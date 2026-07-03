from . import register_tool
from ddgs import DDGS


@register_tool()
def web_search(query: str, max_results: int = 5, timelimit: str = None) -> str:
    """Search the web for current information. Returns title + snippet + URL.
    
    Args:
        query: Search query
        max_results: Number of results (default 5)
        timelimit: Time filter - 'd' (day), 'w' (week), 'm' (month), 'y' (year). Default: None (all time)
    """
    try:
        with DDGS() as ddgs:
            kwargs = {"query": query, "max_results": max_results}
            if timelimit:
                kwargs["timelimit"] = timelimit
            results = list(ddgs.text(**kwargs))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"- {r['title']}: {r['body']} ({r['href']})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching web: {e}"


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
