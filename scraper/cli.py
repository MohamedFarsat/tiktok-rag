import argparse
import os
from datetime import datetime, timezone

from .crawl import crawl
from .export_graph import export_graph
from .fetch import PoliteFetcher
from .robots_check import load_robots_parser
from .robots_rules import default_tiktok_rules


DEFAULT_TIKTOK_START = "https://www.tiktok.com/community-guidelines/en"
DEFAULT_META_START = "https://transparency.meta.com/policies/community-standards/"
DEFAULT_YOUTUBE_START = "https://support.google.com/youtube/answer/9288567?hl=en-GB"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ethical guidelines crawler")
    parser.add_argument("--start", default=None, help="Start URL for a single source")
    parser.add_argument("--out", default="data", help="Output directory")
    parser.add_argument("--max-pages", type=int, default=300, help="Max pages to crawl")
    parser.add_argument(
        "--youtube-max-depth",
        type=int,
        default=2,
        help="Max crawl depth for YouTube policy pages",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=2800,
        help="Maximum characters per chunk before splitting",
    )
    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=200,
        help="Character overlap between split chunks",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N pages (0 to disable)",
    )
    parser.add_argument(
        "--log-requests",
        action="store_true",
        help="Log each request URL and errors",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Request timeout in seconds (omit for no timeout)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retry attempts for a request",
    )
    parser.add_argument(
        "--log-export",
        action="store_true",
        help="Log export merge/write progress",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete existing nodes/edges before running",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append results to existing nodes/edges without merging",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Sources to crawl: tiktok meta youtube",
    )
    parser.add_argument("--source", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources = []
    if args.sources:
        sources = args.sources
    elif args.source:
        sources = [args.source]
    else:
        sources = ["tiktok"]

    if args.start and len(sources) != 1:
        parser.error("--start can only be used with a single source")

    skipped_robots = []
    fetcher = PoliteFetcher(timeout=args.timeout, retries=args.retries)

    if args.fresh:
        nodes_path = os.path.join(args.out, "nodes.jsonl")
        edges_path = os.path.join(args.out, "edges.jsonl")
        if os.path.exists(nodes_path):
            os.remove(nodes_path)
        if os.path.exists(edges_path):
            os.remove(edges_path)

    for source in sources:
        source_key = source.lower().strip()
        if source_key == "tiktok":
            print(f"Starting crawl: {source_key}")
            start_url = args.start or DEFAULT_TIKTOK_START
            result = crawl(
                start_url,
                max_pages=args.max_pages,
                allowed_prefixes=["/community-guidelines/en"],
                rules=default_tiktok_rules(),
                fetcher=fetcher,
                source="tiktok_community_guidelines",
                platforms=["tiktok"],
                progress_every=args.progress_every,
                log_requests=args.log_requests,
            )
        elif source_key == "meta":
            print(f"Starting crawl: {source_key}")
            start_url = args.start or DEFAULT_META_START
            robots = load_robots_parser(start_url, fetcher.user_agent)
            result = crawl(
                start_url,
                max_pages=args.max_pages,
                allowed_prefixes=["/policies/community-standards"],
                rules=None,
                fetcher=fetcher,
                robots=robots,
                source="meta_community_standards",
                platforms=["instagram", "facebook"],
                progress_every=args.progress_every,
                log_requests=args.log_requests,
            )
        elif source_key == "youtube":
            print(f"Starting crawl: {source_key}")
            start_url = args.start or DEFAULT_YOUTUBE_START
            result = crawl(
                start_url,
                max_pages=args.max_pages,
                allowed_prefixes=["/youtube/answer/"],
                rules=None,
                fetcher=fetcher,
                source="youtube_community_guidelines",
                platforms=["youtube"],
                keep_query_params={"hl"},
                youtube_max_depth=args.youtube_max_depth,
                progress_every=args.progress_every,
                log_requests=args.log_requests,
            )
        else:
            parser.error(f"Unknown source: {source}")
        skipped_robots.extend(result.skipped_robots)
        print(f"Finished crawl: {source_key}, pages={len(result.pages)}")

        print("Starting export...")
        counts = export_graph(
            result.pages,
            out_dir=args.out,
            max_chunk_chars=args.max_chunk_chars,
            overlap_chars=args.overlap_chars,
            retrieved_at=retrieved_at,
            log_progress=args.log_export,
            merge_existing=not args.append,
            append=args.append,
        )
        print("Export complete.")

        unique_skipped = []
        seen_skipped = set()
        for url in result.skipped_robots:
            if url not in seen_skipped:
                unique_skipped.append(url)
                seen_skipped.add(url)

        print(f"Validation report [{source_key}]:")
        print(f"Node types: {counts['node_types']}")
        print(f"Edge types: {counts['edge_types']}")
        print(f"Robots skipped URLs: {len(unique_skipped)}")
        if unique_skipped:
            examples = ", ".join(unique_skipped[:5])
            print(f"Robots skipped examples: {examples}")

    unique_skipped_all = []
    seen_skipped_all = set()
    for url in skipped_robots:
        if url not in seen_skipped_all:
            unique_skipped_all.append(url)
            seen_skipped_all.add(url)
    if len(sources) > 1:
        print(f"Robots skipped total: {len(unique_skipped_all)}")


if __name__ == "__main__":
    main()
