from typing import Dict, List, Optional

from .chroma_store import ChromaStore
from .graph_loader import Graph
from .rerank import maybe_create_reranker
from .url_utils import canonicalize_url


def _make_snippet(text: str, max_len: int = 320) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _parse_platforms(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(p).lower() for p in value]
    if isinstance(value, str):
        if value.startswith("|") and value.endswith("|"):
            parts = [p for p in value.strip("|").split("|") if p]
            return [p.lower() for p in parts]
        return [p.strip().lower() for p in value.split(",") if p.strip()]
    return []


class GraphRAGRetriever:
    def __init__(
        self,
        graph: Graph,
        chroma: ChromaStore,
        rerank_model: Optional[str] = None,
        rerank_enabled: bool = True,
        rerank_offline: bool = False,
    ):
        self.graph = graph
        self.chroma = chroma
        self.reranker = maybe_create_reranker(
            rerank_model, enabled=rerank_enabled, offline=rerank_offline
        )

    def retrieve(
        self,
        question: str,
        platforms: Optional[List[str]] = None,
        top_k: int = 20,
        rerank_top_n: int = 10,
    ) -> Dict:
        initial_hits = self.chroma.query(
            query_text=question, top_k=top_k, platforms=platforms
        )

        candidates: Dict[str, Dict] = {}
        for hit in initial_hits:
            chunk_id = hit["chunk_id"]
            if chunk_id not in candidates:
                candidates[chunk_id] = self._chunk_from_hit(hit)
            for neighbor_id in self.graph.get_neighbors(chunk_id):
                if neighbor_id not in candidates and neighbor_id in self.graph.chunks:
                    candidates[neighbor_id] = self._chunk_from_graph(neighbor_id)

        candidate_list = list(candidates.values())
        if self.reranker and candidate_list:
            candidate_list = self.reranker.rerank(
                question, candidate_list, top_n=rerank_top_n
            )

        return self._build_evidence(candidate_list, platforms)

    def _chunk_from_hit(self, hit: Dict) -> Dict:
        chunk_id = hit["chunk_id"]
        chunk = self.graph.chunks.get(chunk_id, {})
        metadata = hit.get("metadata") or {}
        meta_platforms = _parse_platforms(metadata.get("platforms"))
        url = canonicalize_url(metadata.get("url") or chunk.get("url") or "")
        return {
            "chunk_id": chunk_id,
            "text": hit.get("text") or chunk.get("text") or "",
            "platforms": meta_platforms or chunk.get("platforms", []),
            "page_title": metadata.get("page_title")
            or self.graph.get_page_title_for_chunk(chunk_id),
            "heading": metadata.get("heading") or chunk.get("heading"),
            "url": url,
        }

    def _chunk_from_graph(self, chunk_id: str) -> Dict:
        chunk = self.graph.chunks[chunk_id]
        url = canonicalize_url(chunk.get("url") or "")
        return {
            "chunk_id": chunk_id,
            "text": chunk.get("text") or "",
            "platforms": chunk.get("platforms", []),
            "page_title": self.graph.get_page_title_for_chunk(chunk_id),
            "heading": chunk.get("heading"),
            "url": url,
        }

    def _build_evidence(
        self, chunks: List[Dict], platforms: Optional[List[str]]
    ) -> Dict:
        evidence: Dict[str, List[Dict]] = {}
        platform_filter = set(p.lower() for p in platforms or [])
        for chunk in chunks:
            chunk_platforms = [p.lower() for p in chunk.get("platforms", [])]
            if platform_filter and not platform_filter.intersection(chunk_platforms):
                continue
            for platform in chunk_platforms or []:
                if platform_filter and platform not in platform_filter:
                    continue
                evidence.setdefault(platform, []).append(
                    {
                        "page_title": chunk.get("page_title"),
                        "heading": chunk.get("heading"),
                        "snippet": _make_snippet(chunk.get("text", "")),
                        "url": chunk.get("url"),
                        "chunk_id": chunk.get("chunk_id"),
                    }
                )
        return {"platforms": evidence}
