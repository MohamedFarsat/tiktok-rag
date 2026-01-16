from typing import Iterable, List

from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()
