from collections import deque
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

from .fetch import PoliteFetcher
from .parse import parse_html
from .robots_rules import RobotsRules, default_tiktok_rules


@dataclass
class PageData:
    url: str
    final_url: str
    title: str
    chunks: List[dict]
    out_links: List[str]


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def _is_target_path(url: str) -> bool:
    path = urlparse(url).path or "/"
    return path.startswith("/community-guidelines/en")


def crawl(
    start_url: str,
    max_pages: int = 300,
    rules: Optional[RobotsRules] = None,
    fetcher: Optional[PoliteFetcher] = None,
) -> List[PageData]:
    rules = rules or default_tiktok_rules()
    fetcher = fetcher or PoliteFetcher()

    origin = urlunparse(("https", urlparse(start_url).netloc, "", "", "", ""))

    queue = deque([normalize_url(start_url)])
    seen = set()
    pages: List[PageData] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        if not _is_target_path(url):
            continue
        if not rules.is_allowed_url(url, origin):
            continue

        result = fetcher.fetch(url)
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
                and _is_target_path(n)
                and rules.is_allowed_url(n, origin)
            ):
                queue.append(n)

        pages.append(
            PageData(
                url=url,
                final_url=final_url,
                title=title,
                chunks=chunks,
                out_links=normalized_links,
            )
        )

    return pages
