from __future__ import annotations

import os
from typing import Any

import requests


class WebSearchUnavailable(RuntimeError):
    """Raised when operations have not configured a public web search backend."""


def _configured() -> tuple[str, str, str]:
    provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    api_key = os.getenv("WEB_SEARCH_API_KEY", "").strip()
    url = os.getenv("WEB_SEARCH_API_URL", "").strip()
    if provider == "responses":
        api_key = api_key or os.getenv("LLM_API_KEY", "").strip()
        url = url or f"{os.getenv('LLM_API_URL', '').rstrip('/')}/responses"
    elif provider == "tavily":
        url = url or "https://api.tavily.com/search"
    elif provider == "brave":
        url = url or "https://api.search.brave.com/res/v1/web/search"
    if provider not in {"responses", "tavily", "brave"} or not api_key or not url:
        raise WebSearchUnavailable("联网检索未配置")
    return provider, api_key, url


def search_web(query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
    provider, api_key, url = _configured()
    query = str(query or "").strip()
    if not query:
        return []
    if provider == "tavily":
        response = requests.post(
            url,
            json={"api_key": api_key, "query": query, "max_results": min(max_results, 10), "include_answer": False},
            timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "20")),
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results") or []
    elif provider == "brave":
        response = requests.get(
            url,
            params={"q": query, "count": min(max_results, 10), "search_lang": "zh-hans"},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "20")),
        )
        response.raise_for_status()
        rows = (response.json().get("web") or {}).get("results") or []
    else:
        response = requests.post(
            url,
            json={
                "model": os.getenv("WEB_SEARCH_MODEL", os.getenv("LLM_MODEL_NAME", "")),
                "input": query,
                "tools": [{"type": os.getenv("WEB_SEARCH_TOOL_TYPE", "web_search_preview")}],
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "20")),
        )
        response.raise_for_status()
        payload = response.json()
        rows = []
        for output in payload.get("output") or []:
            for content in output.get("content") or []:
                text = content.get("text") if isinstance(content, dict) else None
                if text:
                    annotations = content.get("annotations") or [] if isinstance(content, dict) else []
                    citations = [
                        item for item in annotations
                        if isinstance(item, dict) and item.get("url")
                    ]
                    if citations:
                        for item in citations:
                            rows.append({
                                "title": str(item.get("title") or "联网来源"),
                                "url": str(item.get("url")),
                                "content": text,
                            })
    normalized = []
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        source_url = str(row.get("url") or row.get("link") or "").strip()
        excerpt = str(row.get("content") or row.get("description") or "").strip()
        if not title or not source_url or not excerpt:
            continue
        normalized.append({
            "title": title,
            "url": source_url,
            "publisher": str(row.get("publisher") or row.get("source") or "").strip(),
            "published_at": str(row.get("published_date") or row.get("page_age") or "").strip(),
            "excerpt": excerpt[:6000],
            "kind": "web_result",
        })
    return normalized
