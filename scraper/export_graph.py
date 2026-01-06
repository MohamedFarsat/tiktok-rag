import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .crawl import PageData


def _sha1_id(*parts: str) -> str:
    data = "|".join(parts).encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def _infer_locale(url: str) -> str:
    path = urlparse(url).path or ""
    prefix = "/community-guidelines/"
    if path.startswith(prefix):
        rest = path[len(prefix) :].lstrip("/")
        if rest:
            return rest.split("/", 1)[0]
    return "unknown"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_split_point(text: str, start: int, end: int) -> int:
    length = len(text)
    for i in range(end, start, -1):
        if text[i - 1] in ".!?" and (i == length or text[i].isspace()):
            return i
    for i in range(end, start, -1):
        if text[i - 1].isspace():
            return i
    for i in range(end, length):
        if text[i].isspace():
            return i
    return length


def _split_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    text = text.strip()
    if not text or len(text) <= max_chars:
        return [text] if text else []

    parts = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + max_chars, length)
        split_at = end if end == length else _find_split_point(text, start, end)
        if split_at <= start:
            split_at = end

        part = text[start:split_at].strip()
        if part:
            parts.append(part)

        if split_at >= length:
            break

        next_start = split_at - overlap_chars
        if next_start < 0:
            next_start = 0
        while next_start > 0 and not text[next_start - 1].isspace():
            next_start -= 1
        if next_start >= split_at:
            next_start = split_at
        start = next_start

    return parts


def export_graph(
    pages: List[PageData],
    out_dir: str = "data",
    max_chunk_chars: int = 3500,
    overlap_chars: int = 300,
    retrieved_at: Optional[str] = None,
) -> Dict[str, int]:
    if retrieved_at is None:
        retrieved_at = _utc_now_iso()
    source = "tiktok_community_guidelines"

    os.makedirs(out_dir, exist_ok=True)
    nodes_path = os.path.join(out_dir, "nodes.jsonl")
    edges_path = os.path.join(out_dir, "edges.jsonl")

    node_ids = set()
    edge_ids = set()

    nodes = []
    edges = []

    url_to_page_id = {}
    for page in pages:
        page_id = _sha1_id("PAGE", page.url)
        url_to_page_id[page.url] = page_id

    for page in pages:
        page_id = url_to_page_id[page.url]
        locale = _infer_locale(page.url)
        page_node = {
            "id": page_id,
            "type": "PAGE",
            "url": page.url,
            "title": page.title,
            "locale": locale,
            "source": source,
            "retrieved_at": retrieved_at,
        }
        if page_id not in node_ids:
            nodes.append(page_node)
            node_ids.add(page_id)

        section_ids = {}
        prev_chunk_id = None
        chunk_order = 0
        for chunk in page.chunks:
            heading = chunk["heading"]
            section_id = section_ids.get(heading)
            if section_id is None:
                section_id = _sha1_id("SECTION", page.url, heading)
                section_node = {
                    "id": section_id,
                    "type": "SECTION",
                    "url": page.url,
                    "heading": heading,
                    "source": source,
                    "retrieved_at": retrieved_at,
                }
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

            for part in _split_text(
                chunk["text"], max_chars=max_chunk_chars, overlap_chars=overlap_chars
            ):
                chunk_id = _sha1_id(
                    "CHUNK",
                    page.url,
                    heading,
                    str(chunk_order),
                    part,
                )
                chunk_node = {
                    "id": chunk_id,
                    "type": "CHUNK",
                    "url": page.url,
                    "heading": heading,
                    "order": chunk_order,
                    "text": part,
                    "page_title": page.title,
                    "source": source,
                    "retrieved_at": retrieved_at,
                }
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
                chunk_order += 1

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

    with open(nodes_path, "w", encoding="utf-8") as f:
        for node in nodes:
            f.write(json.dumps(node, ensure_ascii=True) + "\n")

    with open(edges_path, "w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, ensure_ascii=True) + "\n")

    return {"nodes": len(nodes), "edges": len(edges)}
