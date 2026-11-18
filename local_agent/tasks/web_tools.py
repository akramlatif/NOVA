"""Safe Web Tools for NOVA.

Provides lightweight web search and content extraction without heavy external
scraping frameworks. Treats all remote content as untrusted DATA and defends
against SSRF (Server-Side Request Forgery).
"""

from __future__ import annotations

import html
import ipaddress
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import httpx


class WebToolError(Exception):
    """Base exception for web tool operations."""


# Private / loopback CIDR blocks for SSRF prevention
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
]


def _validate_safe_url(url_str: str) -> str:
    """Validate URL scheme and block SSRF targeting localhost or intranet."""
    if not url_str or not url_str.strip():
        raise WebToolError("URL cannot be empty.")

    parsed = urlparse(url_str.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise WebToolError(f"Unsupported URL scheme: {parsed.scheme!r}. Only HTTP/HTTPS permitted.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise WebToolError(f"Invalid URL: {url_str}")

    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise WebToolError("Access to localhost or loopback addresses is forbidden.")

    try:
        ip = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise WebToolError(f"Access to private/intranet IP {hostname} is forbidden.")
    except ValueError:
        # Not a raw IP literal; domain names like example.com pass
        pass

    return url_str.strip()


def _strip_html(raw_html: str) -> str:
    """Extract readable text from HTML by removing scripts, styles, and tags."""
    # 1. Remove script and style elements
    text = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # 2. Replace break and paragraph tags with newlines
    text = re.sub(r"<(?:br|p|div|tr|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    # 3. Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # 4. Unescape HTML entities
    text = html.unescape(text)
    # 5. Collapse excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def web_fetch_text(
    url: str,
    max_length: int = 4000,
    timeout_seconds: float = 10.0,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Fetch a public webpage and extract sanitized text content.

    Untrusted content is strictly treated as DATA, with all scripts and tags
    stripped to prevent prompt injection or code execution.
    """
    safe_url = _validate_safe_url(url)
    headers = {
        "User-Agent": "NOVA-Assistant/0.1 (Windows; Lightweight Research Agent)",
        "Accept": "text/html,application/xhtml+xml,text/plain",
    }

    own_client = client is None
    http = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers)
    try:
        resp = http.get(safe_url)
        resp.raise_for_status()
        raw_text = resp.text
    except httpx.HTTPStatusError as e:
        raise WebToolError(f"HTTP error {e.response.status_code} fetching {safe_url}") from e
    except httpx.RequestError as e:
        raise WebToolError(f"Network error fetching {safe_url}: {e}") from e
    finally:
        if own_client:
            http.close()

    clean_text = _strip_html(raw_text)
    truncated = len(clean_text) > max_length
    if truncated:
        clean_text = clean_text[:max_length] + "\n... [Content Truncated]"

    return {
        "url": safe_url,
        "status_code": resp.status_code,
        "content_length": len(clean_text),
        "truncated": truncated,
        "text": clean_text,
    }


def web_search(
    query: str,
    max_results: int = 5,
    timeout_seconds: float = 10.0,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Perform a lightweight web search using DuckDuckGo HTML without API keys."""
    if not query or not query.strip():
        raise WebToolError("Search query cannot be empty.")

    clean_query = query.strip()
    search_url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    }

    own_client = client is None
    http = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers)
    try:
        resp = http.post(search_url, data={"q": clean_query})
        resp.raise_for_status()
        body = resp.text
    except Exception as e:
        raise WebToolError(f"Search request failed: {e}") from e
    finally:
        if own_client:
            http.close()

    # Parse search results defensively using regex
    results: List[Dict[str, str]] = []
    # DuckDuckGo HTML result snippets pattern: <a class="result__snippet" ...>...</a>
    snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', body, re.DOTALL)
    titles = re.findall(r'<a[^>]+class="result__url"[^>]*>(.*?)</a>', body, re.DOTALL)

    for i in range(min(len(snippets), max_results)):
        snippet_text = _strip_html(snippets[i])
        url_text = _strip_html(titles[i]) if i < len(titles) else ""
        if snippet_text:
            results.append({
                "title": f"Result {i+1}",
                "snippet": snippet_text,
                "url": url_text.strip(),
            })

    return {
        "query": clean_query,
        "count": len(results),
        "results": results,
    }
