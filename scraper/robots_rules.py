from dataclasses import dataclass, field
from fnmatch import fnmatch
from urllib.parse import urlparse


@dataclass
class RobotsRules:
    allow_prefixes: list[str] = field(default_factory=list)
    disallow_patterns: list[str] = field(default_factory=list)

    def is_allowed_url(self, url: str, origin: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        origin_parsed = urlparse(origin)
        if parsed.netloc != origin_parsed.netloc:
            return False
        path = parsed.path or "/"
        full = path
        if parsed.query:
            full = f"{path}?{parsed.query}"
        if not any(path.startswith(prefix) for prefix in self.allow_prefixes):
            return False
        for pattern in self.disallow_patterns:
            if fnmatch(full, pattern) or fnmatch(path, pattern):
                return False
        return True


def default_tiktok_rules() -> RobotsRules:
    return RobotsRules(
        allow_prefixes=[
            "/community-guidelines",
            "/amp",
            "/legal",
            "/safety",
            "/transparency",
            "/about",
            "/forgood",
        ],
        disallow_patterns=[
            "/inapp*",
            "/auth*",
            "/embed/@*",
            "/embed/v2*",
            "/embed/curated*",
            "/link*",
            "*/directory/*",
            "/search/video?*",
            "/search/user?q=*",
            "/search?*",
            "/search/live?*",
            "/shop/view/product/*",
            "/sgtm/g/collect*",
            "/api/share/settings*",
            "/api/recommend/embed_videos*",
            "/discover/trending/detail/*",
            "/discover*",
        ],
    )


def is_allowed_url(url: str, origin: str) -> bool:
    return default_tiktok_rules().is_allowed_url(url, origin)
