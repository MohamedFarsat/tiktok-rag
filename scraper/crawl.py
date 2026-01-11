from collections import deque
from dataclasses import dataclass, field
import re
import time
from typing import List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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


def normalize_url(url: str, keep_query_params: Optional[Sequence[str]] = None) -> str:
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = ""
    if keep_query_params:
        params = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k in keep_query_params
        ]
        if params:
            query = urlencode(params, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _extract_query_defaults(
    url: str, keep_query_params: Optional[Sequence[str]]
) -> dict:
    if not keep_query_params:
        return {}
    defaults = {}
    for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
        if key in keep_query_params and key not in defaults:
            defaults[key] = value
    return defaults


def _apply_default_query_params(url: str, defaults: dict) -> str:
    if not defaults:
        return url
    parsed = urlparse(url)
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    existing_keys = {k for k, _ in existing}
    updated = list(existing)
    for key, value in defaults.items():
        if key not in existing_keys:
            updated.append((key, value))
    if updated == existing:
        return url
    query = urlencode(updated, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def _is_target_path(url: str, prefixes: Sequence[str]) -> bool:
    path = urlparse(url).path or "/"
    return any(path.startswith(prefix) for prefix in prefixes)


def is_youtube_policy_page(page_title: str, h1: str, url: str) -> bool:
    text = f"{page_title} {h1} {url}".lower()
    reject_keywords = [
        "how to",
        "fix",
        "troubleshoot",
        "account",
        "payments",
        "billing",
        "premium",
        "creator support",
        "contact",
        "report a problem",
        "appeal",
        "status",
        "features",
        "watch history",
        "comment settings",
        "upload issues",
        "channel settings",
    ]
    for keyword in reject_keywords:
        if keyword in text:
            return False

    allow_keywords = [
        "community guidelines",
        "violence",
        "violent",
        "dangerous",
        "hate",
        "harassment",
        "sensitive",
        "misinformation",
        "child safety",
        "children",
        "spam",
        "scam",
        "deceptive",
        "regulated",
        "drugs",
        "weapons",
        "firearms",
        "nudity",
        "sexual",
        "suicide",
        "self-harm",
        "extremism",
        "terror",
        "threat",
        "incitement",
    ]
    return any(keyword in text for keyword in allow_keywords)


def crawl(
    start_url: str,
    max_pages: int = 300,
    allowed_prefixes: Optional[Sequence[str]] = None,
    rules: Optional[RobotsRules] = None,
    fetcher: Optional[PoliteFetcher] = None,
    robots: Optional[RobotsCheck] = None,
    source: str = "tiktok_community_guidelines",
    platforms: Optional[List[str]] = None,
    keep_query_params: Optional[Sequence[str]] = None,
    youtube_max_depth: int = 2,
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
    default_query_params = _extract_query_defaults(start_url, keep_query_params)
    normalized_start = normalize_url(
        _apply_default_query_params(start_url, default_query_params),
        keep_query_params=keep_query_params,
    )

    depth_limit = youtube_max_depth if source == "youtube_community_guidelines" else None
    queue = deque([(normalized_start, 0)])
    seen = set()
    queued = {normalized_start}
    skipped_robots = set()
    pages: List[PageData] = []

    while queue and len(pages) < max_pages:
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        if depth_limit is not None and depth > depth_limit:
            continue

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

        final_url = normalize_url(
            _apply_default_query_params(result.final_url, default_query_params),
            keep_query_params=keep_query_params,
        )
        title, h1, chunks, out_links = parse_html(result.content, final_url)
        if source == "youtube_community_guidelines":
            if not is_youtube_policy_page(title, h1, final_url):
                continue

        normalized_links = []
        for link in out_links:
            n = normalize_url(
                _apply_default_query_params(link, default_query_params),
                keep_query_params=keep_query_params,
            )
            if n not in normalized_links:
                normalized_links.append(n)
            if (
                n not in seen
                and n not in queued
                and _is_target_path(n, allowed_prefixes)
                and rules.is_allowed_url(n, origin)
            ):
                if depth_limit is not None and depth + 1 > depth_limit:
                    continue
                if robots and not robots.can_fetch(n):
                    skipped_robots.add(n)
                else:
                    queue.append((n, depth + 1))
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
