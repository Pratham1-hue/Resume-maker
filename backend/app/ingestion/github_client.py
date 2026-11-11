from __future__ import annotations

import asyncio
import base64
import os

import httpx
from typing import Any, Dict, List


class GitHubClient:
    """REST-only GitHub client (no token required).

    Uses the public REST API so ingestion works without a GitHub token
    (60 requests/hour unauthenticated). Set GITHUB_TOKEN to raise the limit
    to 5,000/hour.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client
        self.api_base = "https://api.github.com"
        token = os.getenv("GITHUB_TOKEN", "")
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    async def fetch_all(self, username: str) -> Dict[str, Any]:
        """Fetch user info + repos + READMEs for a GitHub user."""
        username = username.strip().lstrip("@")
        try:
            user = await self._get_json(f"{self.api_base}/users/{username}")
        except Exception:
            return {"username": username, "repos": [], "top_languages": {}, "user": {}}
        if not user:
            return {"username": username, "repos": [], "top_languages": {}, "user": {}}

        try:
            repos = await self._get_json(
                f"{self.api_base}/users/{username}/repos",
                params={"per_page": "30", "sort": "updated"},
            )
        except Exception:
            repos = []
        if not isinstance(repos, list):
            repos = []

        # Skip forks by default (keep original work), cap how many READMEs we fetch.
        own_repos = [r for r in repos if isinstance(r, dict) and not r.get("fork")]
        candidates = (own_repos or repos)[:12]

        readme_texts = await asyncio.gather(
            *[self._fetch_readme(username, r.get("name", "")) for r in candidates],
            return_exceptions=True,
        )
        lang_maps = await asyncio.gather(
            *[self._get_json(r.get("languages_url", "")) for r in candidates],
            return_exceptions=True,
        )

        processed = []
        lang_totals: Dict[str, int] = {}
        for repo, readme, langs in zip(candidates, readme_texts, lang_maps):
            if isinstance(readme, Exception) or not isinstance(readme, str):
                readme = repo.get("description") or ""
            if isinstance(langs, Exception) or not isinstance(langs, dict):
                langs = {}
            for lang, count in langs.items():
                if isinstance(count, (int, float)):
                    lang_totals[lang] = lang_totals.get(lang, 0) + int(count)
            processed.append({
                "name": repo.get("name", ""),
                "html_url": repo.get("html_url", ""),
                "description": repo.get("description") or "",
                "readme": readme,
                "metadata": {
                    "topics": repo.get("topics", []) or self._extract_topics(repo.get("description") or ""),
                    "languages": dict(langs),
                    "stars": repo.get("stargazers_count", 0) or 0,
                },
            })

        total = sum(lang_totals.values()) or 1
        top_languages = {k: v / total for k, v in sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)}

        return {
            "username": username,
            "repos": processed,
            "top_languages": top_languages,
            "user": {
                "login": user.get("login"),
                "name": user.get("name"),
                "bio": user.get("bio"),
                "company": user.get("company"),
                "location": user.get("location"),
                "blog": user.get("blog"),
                "public_repos": user.get("public_repos"),
                "followers": user.get("followers"),
                "following": user.get("following"),
            },
        }

    async def _get_json(self, url: str, params: dict | None = None) -> Any:
        if not url:
            return {}
        resp = await self.http.get(url, headers=self._headers, params=params, timeout=30.0)
        if resp.status_code != 200:
            return {} if params is not None or "/repos" not in url else []
        try:
            return resp.json()
        except Exception:
            return {}

    async def _fetch_readme(self, username: str, repo: str) -> str:
        """Fetch a repo README (first ~4k chars). Returns '' on any failure."""
        if not repo:
            return ""
        try:
            resp = await self.http.get(
                f"{self.api_base}/repos/{username}/{repo}/readme",
                headers={**self._headers, "Accept": "application/vnd.github.raw"},
                timeout=30.0,
            )
            if resp.status_code == 200 and resp.text.strip():
                return resp.text[:4000]
            # Fallback: base64 JSON payload
            resp = await self.http.get(
                f"{self.api_base}/repos/{username}/{repo}/readme",
                headers=self._headers,
                timeout=30.0,
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            content = data.get("content", "")
            if not content:
                return ""
            try:
                return base64.b64decode(content).decode("utf-8", errors="ignore")[:4000]
            except Exception:
                return ""
        except Exception:
            return ""

    @staticmethod
    def _extract_topics(description: str) -> List[str]:
        if not description:
            return []
        stopwords = {"the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "with", "for", "using"}
        tokens = description.lower().split()
        topics = [t.strip(".,;:!?()[]") for t in tokens]
        topics = [t for t in topics if t.isalpha() and t not in stopwords and len(t) > 2]
        return list(dict.fromkeys(topics))[:10]
