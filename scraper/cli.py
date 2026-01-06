import argparse
from datetime import datetime, timezone

from .crawl import crawl
from .export_graph import export_graph
from .robots_rules import default_tiktok_rules


DEFAULT_START = "https://www.tiktok.com/community-guidelines/en"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ethical TikTok guidelines crawler")
    parser.add_argument("--start", default=DEFAULT_START, help="Start URL")
    parser.add_argument("--out", default="data", help="Output directory")
    parser.add_argument("--max-pages", type=int, default=300, help="Max pages to crawl")
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=3500,
        help="Maximum characters per chunk before splitting",
    )
    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=300,
        help="Character overlap between split chunks",
    )
    args = parser.parse_args()

    rules = default_tiktok_rules()
    pages = crawl(args.start, max_pages=args.max_pages, rules=rules)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = export_graph(
        pages,
        out_dir=args.out,
        max_chunk_chars=args.max_chunk_chars,
        overlap_chars=args.overlap_chars,
        retrieved_at=retrieved_at,
    )

    print(f"Crawled pages: {len(pages)}")
    print(f"Nodes written: {counts['nodes']}")
    print(f"Edges written: {counts['edges']}")


if __name__ == "__main__":
    main()
