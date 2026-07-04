"""Web tools: search, fetch a page, get news. No API key required."""
from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..config import settings
from . import tool


def _clean_url(url: str) -> str:
    """DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<real-url>. Unwrap it."""
    url = html.unescape(url)
    if "uddg=" in url:
        try:
            qs = parse_qs(urlparse(url if url.startswith("http") else "https:" + url).query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return url


def _strip_html(raw: str, limit: int = 2000) -> str:
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


@tool(
    "search_web",
    "Search the web for current information and return the top results.",
    {"query": "the search query string"},
)
def search_web(query: str) -> str:
    # Preferred: Tavily (if a key is present) — high quality.
    if settings.tavily_api_key:
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": settings.tavily_api_key, "query": query,
                      "max_results": 5, "include_answer": True},
                timeout=30,
            )
            r.raise_for_status()
            d = r.json()
            out = [f"Answer: {d['answer']}"] if d.get("answer") else []
            for res in d.get("results", []):
                out.append(f"- {res['title']}\n  {res['url']}\n  {res.get('content','')[:200]}")
            return "\n".join(out) or "No results."
        except Exception:
            pass  # fall through to free search

    # Free fallback: DuckDuckGo HTML endpoint (no key).
    try:
        r = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (ULTRON)"},
            timeout=30,
            follow_redirects=True,
        )
        r.raise_for_status()
        results = re.findall(
            r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.text, flags=re.S
        )
        snippets = re.findall(r'result__snippet"[^>]*>(.*?)</a>', r.text, flags=re.S)
        if not results:
            return f"No results found for '{query}'."
        out = []
        for i, (url, title) in enumerate(results[:5]):
            snip = _strip_html(snippets[i], 220) if i < len(snippets) else ""
            out.append(f"{i+1}. {_strip_html(title, 120)}\n   {_clean_url(url)}\n   {snip}")
        return f"Search results for '{query}':\n" + "\n".join(out)
    except Exception as e:
        return f"Search failed: {e}"


@tool(
    "fetch_url",
    "Fetch a web page and return its readable text content.",
    {"url": "the full http(s) URL to fetch"},
)
def fetch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (ULTRON)"},
                      timeout=30, follow_redirects=True)
        r.raise_for_status()
        return f"Content of {url}:\n{_strip_html(r.text, 3000)}"
    except Exception as e:
        return f"Failed to fetch {url}: {e}"


@tool(
    "get_news",
    "Get current news headlines, optionally about a topic.",
    {"topic": "topic to search headlines for, e.g. 'technology' or 'world'"},
)
def get_news(topic: str = "world") -> str:
    # Google News RSS — free, no key.
    q = topic.replace(" ", "%20")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (ULTRON)"}, timeout=30)
        r.raise_for_status()
        titles = re.findall(r"<title>(.*?)</title>", r.text, flags=re.S)[1:8]
        if not titles:
            return f"No news found for '{topic}'."
        heads = "\n".join(f"- {html.unescape(t.strip())}" for t in titles)
        return f"Top '{topic}' headlines:\n{heads}"
    except Exception as e:
        return f"News fetch failed: {e}"
