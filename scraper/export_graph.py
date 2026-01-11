import hashlib
import json
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .crawl import PageData


def _sha1_id(*parts: str) -> str:
    """
    Streaming SHA1 to avoid building giant intermediate strings.
    """
    h = hashlib.sha1()
    for i, p in enumerate(parts):
        if i:
            h.update(b"|")
        h.update(p.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _text_sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _split_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    if max_chars <= 0:
        return [text]
    if len(text) <= max_chars:
        return [text]
    overlap = max(0, min(overlap_chars, max_chars - 1))
    parts = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return parts


def _split_chunks(
    chunks: List[dict], max_chunk_chars: int, overlap_chars: int
) -> List[dict]:
    split_chunks = []
    order = 0
    for chunk in chunks:
        heading = chunk["heading"]
        for text in _split_text(chunk["text"], max_chunk_chars, overlap_chars):
            split_chunks.append({"heading": heading, "order": order, "text": text})
            order += 1
    return split_chunks


def _infer_locale(url: str) -> str:
    path = urlparse(url).path or ""
    prefix = "/community-guidelines/"
    if path.startswith(prefix):
        rest = path[len(prefix) :].lstrip("/")
        if rest:
            return rest.split("/", 1)[0]
    return "unknown"


def _load_jsonl(path: str) -> List[dict]:
    items = []
    if not os.path.exists(path):
        return items
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def export_graph(
    pages: List[PageData],
    out_dir: str = "data",
    max_chunk_chars: int = 2800,
    overlap_chars: int = 200,
    retrieved_at: Optional[str] = None,
    log_progress: bool = False,
    merge_existing: bool = True,
    append: bool = False,
) -> Dict[str, int]:
    os.makedirs(out_dir, exist_ok=True)
    nodes_path = os.path.join(out_dir, "nodes.jsonl")
    edges_path = os.path.join(out_dir, "edges.jsonl")

    node_ids = set()
    edge_ids = set()

    nodes = []
    edges = []

    if merge_existing and not append:
        existing_nodes = _load_jsonl(nodes_path)
        existing_edges = _load_jsonl(edges_path)
        for node in existing_nodes:
            node_id = node.get("id")
            if not node_id or node_id in node_ids:
                continue
            nodes.append(node)
            node_ids.add(node_id)
        for edge in existing_edges:
            edge_id = edge.get("id")
            if not edge_id or edge_id in edge_ids:
                continue
            edges.append(edge)
            edge_ids.add(edge_id)

    url_to_page_id = {}
    for page in pages:
        page_id = _sha1_id("PAGE", page.url)
        url_to_page_id[page.url] = page_id

    total_pages = len(pages)
    chunk_count = 0

    for pi, page in enumerate(pages, start=1):
        if pi % 5 == 0 or pi == 1 or pi == total_pages:
            print(f"[export] page {pi}/{total_pages}: {page.url}")

        page_id = url_to_page_id[page.url]
        locale = _infer_locale(page.url)

        page_node = {
            "id": page_id,
            "type": "PAGE",
            "url": page.url,
            "title": page.title,
            "locale": locale,
            "source": page.source,
        }
        if retrieved_at:
            page_node["retrieved_at"] = retrieved_at
        if page.platforms is not None:
            page_node["platforms"] = page.platforms
        if page_id not in node_ids:
            nodes.append(page_node)
            node_ids.add(page_id)

        section_ids = {}
        prev_chunk_id = None

        page_chunks = _split_chunks(page.chunks, max_chunk_chars, overlap_chars)
        for chunk in page_chunks:
            heading = chunk["heading"]
            section_id = section_ids.get(heading)

            if section_id is None:
                section_id = _sha1_id("SECTION", page.url, heading)
                section_node = {
                    "id": section_id,
                    "type": "SECTION",
                    "url": page.url,
                    "heading": heading,
                    "source": page.source,
                }
                if retrieved_at:
                    section_node["retrieved_at"] = retrieved_at
                if page.platforms is not None:
                    section_node["platforms"] = page.platforms
                if section_id not in node_ids:
                    nodes.append(section_node)
                    node_ids.add(section_id)

                edge_id = _sha1_id("PAGE_CONTAINS_SECTION", page_id, section_id)
                if edge_id not in edge_ids:
                    edges.append(
                        {
                            "id": edge_id,
                            "type": "PAGE_CONTAINS_SECTION",
                            "source": page_id,
                            "target": section_id,
                        }
                    )
                    edge_ids.add(edge_id)

                section_ids[heading] = section_id

            # Fast chunk id: use a short hash of the text, not the text itself
            text_hash = _text_sha1(chunk["text"])
            chunk_id = _sha1_id("CHUNK", page.url, heading, str(chunk["order"]), text_hash)

            chunk_node = {
                "id": chunk_id,
                "type": "CHUNK",
                "url": page.url,
                "heading": heading,
                "order": chunk["order"],
                "text": chunk["text"],
                "page_title": page.title,
                "source": page.source,
            }
            if retrieved_at:
                chunk_node["retrieved_at"] = retrieved_at
            if page.platforms is not None:
                chunk_node["platforms"] = page.platforms
            if chunk_id not in node_ids:
                nodes.append(chunk_node)
                node_ids.add(chunk_id)

            edge_id = _sha1_id("SECTION_CONTAINS_CHUNK", section_id, chunk_id)
            if edge_id not in edge_ids:
                edges.append(
                    {
                        "id": edge_id,
                        "type": "SECTION_CONTAINS_CHUNK",
                        "source": section_id,
                        "target": chunk_id,
                    }
                )
                edge_ids.add(edge_id)

            if prev_chunk_id:
                edge_id = _sha1_id("NEXT_CHUNK", prev_chunk_id, chunk_id)
                if edge_id not in edge_ids:
                    edges.append(
                        {
                            "id": edge_id,
                            "type": "NEXT_CHUNK",
                            "source": prev_chunk_id,
                            "target": chunk_id,
                        }
                    )
                    edge_ids.add(edge_id)

            prev_chunk_id = chunk_id
            chunk_count += 1

            if chunk_count % 50 == 0:
                print(f"[export] processed chunks: {chunk_count}")

    for page in pages:
        source_id = url_to_page_id.get(page.url)
        for link in page.out_links:
            target_id = url_to_page_id.get(link)
            if not target_id:
                continue
            edge_id = _sha1_id("PAGE_LINKS_TO_PAGE", source_id, target_id)
            if edge_id not in edge_ids:
                edges.append(
                    {
                        "id": edge_id,
                        "type": "PAGE_LINKS_TO_PAGE",
                        "source": source_id,
                        "target": target_id,
                    }
                )
                edge_ids.add(edge_id)

    # Faster output (and keeps unicode readable)
    node_mode = "a" if append else "w"
    edge_mode = "a" if append else "w"

    with open(nodes_path, node_mode, encoding="utf-8") as f:
        for node in nodes:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")

    with open(edges_path, edge_mode, encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

    node_types: Dict[str, int] = {}
    for node in nodes:
        node_type = node.get("type", "UNKNOWN")
        node_types[node_type] = node_types.get(node_type, 0) + 1

    edge_types: Dict[str, int] = {}
    for edge in edges:
        edge_type = edge.get("type", "UNKNOWN")
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

    print(f"[export] done. nodes={len(nodes)} edges={len(edges)}")
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "node_types": node_types,
        "edge_types": edge_types,
    }
