from dataclasses import dataclass
import hashlib
import json
import os
import random
import time
from typing import Optional

import requests


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: Optional[int]
    content: Optional[str]
    headers: dict
    from_cache: bool
    error: Optional[str]


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: str = ".cache",
        user_agent: str = "TiktokGuidelinesCrawler/1.0",
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: float = 20.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _cache_paths(self, url: str) -> tuple[str, str]:
        key = self._cache_key(url)
        return (
            os.path.join(self.cache_dir, f"{key}.html"),
            os.path.join(self.cache_dir, f"{key}.json"),
        )

    def _load_cache(self, url: str) -> Optional[dict]:
        html_path, meta_path = self._cache_paths(url)
        if not os.path.exists(html_path) or not os.path.exists(meta_path):
            return None
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["content"] = content
            return meta
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cache(self, url: str, content: str, response: requests.Response) -> None:
        html_path, meta_path = self._cache_paths(url)
        meta = {
            "url": url,
            "final_url": response.url,
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "headers": dict(response.headers),
        }
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

    def _sleep_delay(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def fetch(self, url: str) -> FetchResult:
        cached = self._load_cache(url)
        conditional_headers = {}
        if cached:
            if cached.get("etag"):
                conditional_headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                conditional_headers["If-Modified-Since"] = cached["last_modified"]

        for attempt in range(self.retries + 1):
            self._sleep_delay()
            try:
                response = self.session.get(
                    url,
                    headers=conditional_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                status = response.status_code
                if status == 304 and cached:
                    return FetchResult(
                        url=url,
                        final_url=cached.get("final_url", url),
                        status_code=status,
                        content=cached.get("content"),
                        headers=cached.get("headers", {}),
                        from_cache=True,
                        error=None,
                    )
                if status >= 500 or status == 429:
                    raise requests.RequestException(f"retryable status {status}")

                content = response.text if response.text is not None else ""
                if status == 200:
                    self._save_cache(url, content, response)
                return FetchResult(
                    url=url,
                    final_url=response.url,
                    status_code=status,
                    content=content,
                    headers=dict(response.headers),
                    from_cache=False,
                    error=None,
                )
            except Exception as exc:
                if attempt >= self.retries:
                    return FetchResult(
                        url=url,
                        final_url=url,
                        status_code=None,
                        content=None,
                        headers={},
                        from_cache=False,
                        error=str(exc),
                    )
                backoff = self.backoff_factor * (2 ** attempt)
                time.sleep(backoff + random.uniform(0, 0.5))

        return FetchResult(
            url=url,
            final_url=url,
            status_code=None,
            content=None,
            headers={},
            from_cache=False,
            error="unknown failure",
        )
