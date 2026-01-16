from typing import Dict, List, Optional

import chromadb

from .embeddings import Embedder
from .graph_loader import Graph
from .url_utils import canonicalize_url


class ChromaStore:
    def __init__(self, chroma_dir: str, collection_name: str, embedder: Embedder):
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        self.embedder = embedder

    def build_index(self, graph: Graph, batch_size: int = 128) -> None:
        chunk_ids = list(graph.chunks.keys())
        for i in range(0, len(chunk_ids), batch_size):
            batch_ids = chunk_ids[i : i + batch_size]
            texts: List[str] = []
            metadatas: List[Dict] = []
            for chunk_id in batch_ids:
                chunk = graph.chunks[chunk_id]
                platforms = chunk.get("platforms", [])
                platform_blob = "|" + "|".join(platforms) + "|" if platforms else ""
                text = chunk.get("text") or ""
                url = canonicalize_url(chunk.get("url") or "")
                platform_flags = {f"platform_{p}": True for p in platforms}
                texts.append(text)
                metadatas.append(
                    {
                        "chunk_id": chunk_id,
                        "platforms": platform_blob,
                        "page_title": graph.get_page_title_for_chunk(chunk_id),
                        "heading": chunk.get("heading"),
                        "url": url,
                        **platform_flags,
                    }
                )
            embeddings = self.embedder.embed(texts)
            self.collection.upsert(
                ids=batch_ids, embeddings=embeddings, documents=texts, metadatas=metadatas
            )

    def query(
        self, query_text: str, top_k: int = 20, platforms: Optional[List[str]] = None
    ) -> List[Dict]:
        where = None
        if platforms:
            normalized = [p.lower() for p in platforms]
            clauses = [{f"platform_{p}": {"$eq": True}} for p in normalized]
            if len(clauses) == 1:
                where = clauses[0]
            else:
                where = {"$or": clauses}
        query_emb = self.embedder.embed([query_text])[0]
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: List[Dict] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc,
                    "metadata": meta or {},
                    "distance": dist,
                }
            )
        return hits
