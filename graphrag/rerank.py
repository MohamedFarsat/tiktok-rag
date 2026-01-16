import os
import time
from functools import lru_cache
from typing import Dict, List, Optional


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if not value:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def _offline_requested() -> bool:
    return (
        _env_flag("GRAPHRAG_RERANK_OFFLINE")
        or _env_flag("HF_HUB_OFFLINE")
        or _env_flag("TRANSFORMERS_OFFLINE")
    )


def _configure_hf_timeouts() -> None:
    os.environ.setdefault("HF_HUB_HTTP_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")


def _has_local_model(model_name: str) -> bool:
    if os.path.isdir(model_name):
        return True
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        return False
    try:
        snapshot_download(repo_id=model_name, local_files_only=True)
        return True
    except Exception:
        return False


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def _load_with_retry(model_name: str, max_retries: int = 3):
    _configure_hf_timeouts()
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            return _load_cross_encoder(model_name)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep(2 ** attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError("Failed to load reranker model")


class CrossEncoderReranker:
    def __init__(self, model_name: str, offline: bool = False):
        self.model_name = model_name
        self._model = None
        self._disabled = False
        self.offline = offline or _offline_requested()

    def _load(self) -> None:
        if self._model is not None or self._disabled:
            return
        if self.offline and not _has_local_model(self.model_name):
            print(
                f"[graphrag] Reranker disabled: offline mode and model not cached: {self.model_name}"
            )
            self._disabled = True
            return
        try:
            self._model = _load_with_retry(self.model_name)
        except Exception as exc:
            print(
                f"[graphrag] Reranker disabled: failed to load {self.model_name} ({exc.__class__.__name__})."
            )
            self._disabled = True

    def rerank(self, query: str, candidates: List[Dict], top_n: int) -> List[Dict]:
        if not candidates:
            return []
        self._load()
        if self._model is None:
            return candidates
        pairs = [(query, c["text"]) for c in candidates]
        scores = self._model.predict(pairs).tolist()
        scored = list(zip(scores, candidates))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_n]]


def maybe_create_reranker(
    model_name: Optional[str], enabled: bool = True, offline: bool = False
) -> Optional[CrossEncoderReranker]:
    if not enabled or not model_name:
        return None
    try:
        return CrossEncoderReranker(model_name, offline=offline)
    except Exception:
        return None
