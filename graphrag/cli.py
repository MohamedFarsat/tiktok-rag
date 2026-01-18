import argparse
import json
from collections import Counter

from .config import Config
from .graph_loader import Graph
from .chroma_store import ChromaStore
from .embeddings import Embedder
from .retriever import GraphRAGRetriever
from .answer_formatter import format_response, validate_response
from .ollama_client import (
    DEFAULT_LLM_MODEL,
    FALLBACK_LLM_MODEL,
    OllamaClient,
    OllamaError,
)
from .url_utils import is_youtube_support_url


def build_index(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    nodes = args.nodes or cfg.nodes_path
    edges = args.edges or cfg.edges_path
    chroma_dir = args.chroma_dir or cfg.chroma_dir
    graph = Graph.load(nodes, edges)
    embedder = Embedder(cfg.embed_model)
    store = ChromaStore(chroma_dir, cfg.collection_name, embedder)
    store.build_index(graph)
    print(f"Indexed {len(graph.chunks)} chunks into {chroma_dir}")


def query_index(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    nodes = args.nodes or cfg.nodes_path
    edges = args.edges or cfg.edges_path
    chroma_dir = args.chroma_dir or cfg.chroma_dir
    graph = Graph.load(nodes, edges)
    embedder = Embedder(cfg.embed_model)
    store = ChromaStore(chroma_dir, cfg.collection_name, embedder)
    retriever = GraphRAGRetriever(
        graph,
        store,
        rerank_model=cfg.rerank_model,
        rerank_enabled=not args.no_rerank,
        rerank_offline=cfg.rerank_offline,
    )
    evidence = retriever.retrieve(
        question=args.question,
        platforms=args.platforms,
        top_k=args.top_k or cfg.top_k,
        rerank_top_n=args.rerank_top_n or cfg.rerank_top_n,
    )
    response = format_response(
        args.question,
        evidence.get("platforms", {}),
        use_llm=args.use_llm,
        llm_model=args.llm_model,
    )
    validate_response(response)
    print(json.dumps(response, indent=2))


def validate_graph(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    nodes = args.nodes or cfg.nodes_path
    edges = args.edges or cfg.edges_path
    graph = Graph.load(nodes, edges)
    platform_counts: Counter = Counter()
    youtube_keys: dict = {}
    for chunk in graph.chunks.values():
        for platform in chunk.get("platforms", []):
            platform_counts[platform] += 1
        url = chunk.get("url") or ""
        if is_youtube_support_url(url):
            key = (url, chunk.get("heading") or "", chunk.get("order"))
            youtube_keys[key] = youtube_keys.get(key, 0) + 1
    duplicate_youtube = sum(1 for count in youtube_keys.values() if count > 1)
    print("Platform counts:")
    for platform in sorted(platform_counts):
        print(f"- {platform}: {platform_counts[platform]}")
    print(f"YouTube duplicate canonical URLs: {duplicate_youtube}")


def ollama_check(args: argparse.Namespace) -> None:
    client = OllamaClient()
    try:
        models = client.list_models()
    except OllamaError as exc:
        print("Ollama is not reachable at http://127.0.0.1:11434.")
        print(f"Details: {exc}")
        print(f"Suggested command: ollama pull {DEFAULT_LLM_MODEL}")
        return
    print("Ollama is reachable at http://127.0.0.1:11434.")
    if DEFAULT_LLM_MODEL in models:
        print(f"Model available: {DEFAULT_LLM_MODEL}")
        return
    fallback_note = ""
    if FALLBACK_LLM_MODEL in models:
        fallback_note = f" (fallback {FALLBACK_LLM_MODEL} is available)"
    print(f"Default model not found: {DEFAULT_LLM_MODEL}{fallback_note}.")
    print(f"Suggested command: ollama pull {DEFAULT_LLM_MODEL}")


def sanity_llm(args: argparse.Namespace) -> None:
    question = "Are graphic violence videos allowed?"
    evidence = {
        "tiktok": [
            {
                "page_title": "TikTok Community Guidelines",
                "heading": "Violent and graphic content",
                "snippet": (
                "We don't allow anything extremely gory, disturbing, or violent. "
                "Some content that's less graphic or shared in the public interest may be allowed."
                ),
                "url": "https://www.tiktok.com/community-guidelines",
            },
            {
                "page_title": "TikTok Community Guidelines",
                "heading": "Public interest exceptions",
                "snippet": (
                    "Content that documents violence in the public interest may be allowed "
                    "when it is not overly graphic."
                ),
                "url": "https://www.tiktok.com/community-guidelines",
            },
        ]
    }
    response = format_response(
        question,
        evidence,
        use_llm=True,
        llm_model=DEFAULT_LLM_MODEL,
    )
    answer = response.get("platforms", {}).get("tiktok", {}).get("answer", "")
    print(answer)


def main() -> None:
    parser = argparse.ArgumentParser(prog="graphrag")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build ChromaDB index")
    build.add_argument("--nodes", help="Path to nodes.jsonl")
    build.add_argument("--edges", help="Path to edges.jsonl")
    build.add_argument("--chroma-dir", help="ChromaDB directory")
    build.set_defaults(func=build_index)

    query = sub.add_parser("query", help="Query Graph-RAG")
    query.add_argument("--nodes", help="Path to nodes.jsonl")
    query.add_argument("--edges", help="Path to edges.jsonl")
    query.add_argument("--chroma-dir", help="ChromaDB directory")
    query.add_argument("--question", required=True)
    query.add_argument("--platforms", nargs="*", default=[])
    query.add_argument("--top-k", type=int)
    query.add_argument("--rerank-top-n", type=int)
    query.add_argument("--no-rerank", action="store_true")
    llm_group = query.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", dest="use_llm", action="store_true")
    llm_group.add_argument("--no-llm", dest="use_llm", action="store_false")
    query.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    query.set_defaults(use_llm=True)
    query.set_defaults(func=query_index)

    validate = sub.add_parser("validate", help="Validate nodes and edges")
    validate.add_argument("--nodes", help="Path to nodes.jsonl")
    validate.add_argument("--edges", help="Path to edges.jsonl")
    validate.set_defaults(func=validate_graph)

    ollama = sub.add_parser("ollama-check", help="Check Ollama connectivity")
    ollama.set_defaults(func=ollama_check)

    sanity = sub.add_parser("sanity-llm", help="Run a guardrail sanity check")
    sanity.set_defaults(func=sanity_llm)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
