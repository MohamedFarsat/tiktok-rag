from urllib.parse import urlencode, urlparse, urlunparse


def is_youtube_support_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host == "support.google.com" and (parsed.path or "").startswith(
        "/youtube/answer/"
    )


def canonicalize_url(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    if not is_youtube_support_url(url):
        return url
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or (parsed.hostname or "support.google.com")
    query = urlencode({"hl": "en-GB"})
    return urlunparse((scheme, netloc, parsed.path, "", query, ""))
