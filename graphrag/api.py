from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .config import Config
from .graph_loader import Graph
from .chroma_store import ChromaStore
from .embeddings import Embedder
from .retriever import GraphRAGRetriever
from .answer_formatter import format_response, validate_response

app = FastAPI(title="GraphRAG API")


class QueryRequest(BaseModel):
    question: str
    platforms: List[str] = []
    top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None


def _build_retriever() -> GraphRAGRetriever:
    cfg = Config.from_env()
    graph = Graph.load(cfg.nodes_path, cfg.edges_path)
    embedder = Embedder(cfg.embed_model)
    chroma = ChromaStore(cfg.chroma_dir, cfg.collection_name, embedder)
    return GraphRAGRetriever(graph, chroma, rerank_model=cfg.rerank_model)


_RETRIEVER = _build_retriever()
_CONFIG = Config.from_env()


@app.post("/query")
def query(req: QueryRequest):
    raw = _RETRIEVER.retrieve(
        question=req.question,
        platforms=req.platforms,
        top_k=req.top_k or _CONFIG.top_k,
        rerank_top_n=req.rerank_top_n or _CONFIG.rerank_top_n,
    )
    response = format_response(req.question, raw.get("platforms", {}))
    validate_response(response)
    return response
