from dataclasses import dataclass
import os


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if not value:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    nodes_path: str = "nodes.jsonl"
    edges_path: str = "edges.jsonl"
    chroma_dir: str = ".chroma"
    collection_name: str = "chunks"
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 20
    rerank_top_n: int = 10
    rerank_offline: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            nodes_path=os.getenv("GRAPHRAG_NODES", cls.nodes_path),
            edges_path=os.getenv("GRAPHRAG_EDGES", cls.edges_path),
            chroma_dir=os.getenv("GRAPHRAG_CHROMA_DIR", cls.chroma_dir),
            collection_name=os.getenv("GRAPHRAG_COLLECTION", cls.collection_name),
            embed_model=os.getenv("GRAPHRAG_EMBED_MODEL", cls.embed_model),
            rerank_model=os.getenv("GRAPHRAG_RERANK_MODEL", cls.rerank_model),
            top_k=int(os.getenv("GRAPHRAG_TOP_K", cls.top_k)),
            rerank_top_n=int(os.getenv("GRAPHRAG_RERANK_TOP_N", cls.rerank_top_n)),
            rerank_offline=(
                _env_flag("GRAPHRAG_RERANK_OFFLINE")
                or _env_flag("HF_HUB_OFFLINE")
                or _env_flag("TRANSFORMERS_OFFLINE")
            ),
        )
