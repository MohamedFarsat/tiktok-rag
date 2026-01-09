from collections import deque
from dataclasses import dataclass, field
import re
import time
from typing import List, Optional, Sequence
from urllib.parse import urlparse, urlunparse

from .fetch import PoliteFetcher
from .parse import parse_html
from .robots_check import RobotsCheck
from .robots_rules import RobotsRules, default_tiktok_rules


@dataclass
class PageData:
    url: str
    final_url: str
    title: str
    chunks: List[dict]
    out_links: List[str]
    source: str
    platforms: Optional[List[str]] = None


@dataclass
class CrawlResult:
    pages: List[PageData] = field(default_factory=list)
    skipped_robots: List[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def _is_target_path(url: str, prefixes: Sequence[str]) -> bool:
    path = urlparse(url).path or "/"
    return any(path.startswith(prefix) for prefix in prefixes)


def crawl(
    start_url: str,
    max_pages: int = 300,
    allowed_prefixes: Optional[Sequence[str]] = None,
    rules: Optional[RobotsRules] = None,
    fetcher: Optional[PoliteFetcher] = None,
    robots: Optional[RobotsCheck] = None,
    source: str = "tiktok_community_guidelines",
    platforms: Optional[List[str]] = None,
    progress_every: int = 10,
    log_requests: bool = False,
) -> CrawlResult:
    fetcher = fetcher or PoliteFetcher()
    allowed_prefixes = allowed_prefixes or ["/community-guidelines/en"]
    if rules is None:
        if source == "tiktok_community_guidelines":
            rules = default_tiktok_rules()
        else:
            rules = RobotsRules(
                allow_prefixes=list(allowed_prefixes), disallow_patterns=[]
            )

    origin = urlunparse(("https", urlparse(start_url).netloc, "", "", "", ""))

    queue = deque([normalize_url(start_url)])
    seen = set()
    queued = {normalize_url(start_url)}
    skipped_robots = set()
    pages: List[PageData] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        if not _is_target_path(url, allowed_prefixes):
            continue
        if not rules.is_allowed_url(url, origin):
            continue
        if robots and not robots.can_fetch(url):
            skipped_robots.add(url)
            continue

        if log_requests:
            print(f"Fetching [{source}]: {url}")
        start_ts = time.monotonic()
        result = fetcher.fetch(url)
        elapsed = time.monotonic() - start_ts
        if log_requests:
            status = result.status_code if result.status_code is not None else "n/a"
            print(f"Fetched [{source}]: {url} status={status} in {elapsed:.2f}s")
            if result.error:
                print(f"Fetch error [{source}]: {url} -> {result.error}")
        if not result.content:
            continue

        final_url = normalize_url(result.final_url)
        title, chunks, out_links = parse_html(result.content, final_url)

        normalized_links = []
        for link in out_links:
            n = normalize_url(link)
            if n not in normalized_links:
                normalized_links.append(n)
            if (
                n not in seen
                and n not in queued
                and _is_target_path(n, allowed_prefixes)
                and rules.is_allowed_url(n, origin)
            ):
                if robots and not robots.can_fetch(n):
                    skipped_robots.add(n)
                else:
                    queue.append(n)
                    queued.add(n)

        pages.append(
            PageData(
                url=url,
                final_url=final_url,
                title=title,
                chunks=chunks,
                out_links=normalized_links,
                source=source,
                platforms=platforms,
            )
        )
        if progress_every > 0 and len(pages) % progress_every == 0:
            print(
                f"Progress [{source}]: {len(pages)} pages, queue={len(queue)}, skipped_robots={len(skipped_robots)}"
            )

    return CrawlResult(pages=pages, skipped_robots=sorted(skipped_robots))
