from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Config
from .graph_loader import Graph
from .chroma_store import ChromaStore
from .embeddings import Embedder
from .retriever import GraphRAGRetriever
from .answer_formatter import format_response, validate_response
from .ollama_client import DEFAULT_LLM_MODEL

app = FastAPI(title="GraphRAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str
    platforms: List[str] = []
    top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None
    use_llm: bool = True
    llm_model: str = DEFAULT_LLM_MODEL


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
    response = format_response(
        req.question,
        raw.get("platforms", {}),
        use_llm=req.use_llm,
        llm_model=req.llm_model,
    )
    validate_response(response)
    return response
