import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .url_utils import canonicalize_url, is_youtube_support_url


PLATFORM_HOST_MAP = {
    "tiktok.com": ["tiktok"],
    "transparency.meta.com": ["instagram", "facebook"],
    "support.google.com": ["youtube"],
}


def _infer_platforms(node: dict) -> List[str]:
    if "platform" in node and node["platform"]:
        return [str(node["platform"]).lower()]
    if "platforms" in node and node["platforms"]:
        return [str(p).lower() for p in node["platforms"]]
    url = node.get("url") or ""
    host = (urlparse(url).hostname or "").lower()
    for suffix, platforms in PLATFORM_HOST_MAP.items():
        if host == suffix or host.endswith("." + suffix):
            return list(platforms)
    return []


def _youtube_chunk_key(node: dict) -> Optional[tuple]:
    url = node.get("url") or ""
    if not is_youtube_support_url(url):
        return None
    return (url, node.get("heading") or "", node.get("order"))


@dataclass
class Graph:
    pages: Dict[str, dict]
    sections: Dict[str, dict]
    chunks: Dict[str, dict]
    chunk_to_section: Dict[str, str]
    section_to_page: Dict[str, str]
    section_to_chunks: Dict[str, List[str]]
    page_to_sections: Dict[str, List[str]]
    next_chunk: Dict[str, str]
    prev_chunk: Dict[str, str]

    @classmethod
    def load(cls, nodes_path: str, edges_path: str) -> "Graph":
        pages: Dict[str, dict] = {}
        sections: Dict[str, dict] = {}
        chunks: Dict[str, dict] = {}
        seen_youtube_chunk_keys: set = set()

        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                node = json.loads(line)
                node_type = node.get("type")
                node_id = node.get("id")
                if not node_id or not node_type:
                    continue
                if node.get("url"):
                    node["url"] = canonicalize_url(node["url"])
                if node_type == "PAGE":
                    pages[node_id] = node
                elif node_type == "SECTION":
                    sections[node_id] = node
                elif node_type == "CHUNK":
                    platforms = _infer_platforms(node)
                    node["platforms"] = platforms
                    key = _youtube_chunk_key(node)
                    if key:
                        if key in seen_youtube_chunk_keys:
                            continue
                        seen_youtube_chunk_keys.add(key)
                    chunks[node_id] = node

        chunk_to_section: Dict[str, str] = {}
        section_to_page: Dict[str, str] = {}
        section_to_chunks: Dict[str, List[str]] = defaultdict(list)
        page_to_sections: Dict[str, List[str]] = defaultdict(list)
        next_chunk: Dict[str, str] = {}
        prev_chunk: Dict[str, str] = {}

        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                edge = json.loads(line)
                edge_type = edge.get("type")
                source = edge.get("source")
                target = edge.get("target")
                if edge_type == "SECTION_CONTAINS_CHUNK" and source and target:
                    section_to_chunks[source].append(target)
                    chunk_to_section[target] = source
                elif edge_type == "PAGE_CONTAINS_SECTION" and source and target:
                    page_to_sections[source].append(target)
                    section_to_page[target] = source
                elif edge_type == "NEXT_CHUNK" and source and target:
                    next_chunk[source] = target
                    prev_chunk[target] = source

        return cls(
            pages=pages,
            sections=sections,
            chunks=chunks,
            chunk_to_section=chunk_to_section,
            section_to_page=section_to_page,
            section_to_chunks=section_to_chunks,
            page_to_sections=page_to_sections,
            next_chunk=next_chunk,
            prev_chunk=prev_chunk,
        )

    def get_page_title_for_chunk(self, chunk_id: str) -> Optional[str]:
        chunk = self.chunks.get(chunk_id, {})
        if chunk.get("page_title"):
            return chunk["page_title"]
        section_id = self.chunk_to_section.get(chunk_id)
        page_id = self.section_to_page.get(section_id) if section_id else None
        page = self.pages.get(page_id) if page_id else None
        return page.get("title") if page else None

    def get_neighbors(self, chunk_id: str) -> List[str]:
        neighbors: List[str] = []
        prev_id = self.prev_chunk.get(chunk_id)
        next_id = self.next_chunk.get(chunk_id)
        if prev_id:
            neighbors.append(prev_id)
        if next_id:
            neighbors.append(next_id)
        return neighbors
