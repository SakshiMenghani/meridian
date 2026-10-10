import hashlib
import math
import os
import re
from functools import lru_cache

TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "of",
    "to",
    "and",
    "or",
    "me",
    "you",
    "can",
    "please",
    "do",
    "does",
    "did",
    "how",
    "what",
    "which",
    "who",
    "that",
    "this",
    "these",
    "those",
    "in",
    "on",
    "for",
    "with",
    "from",
    "by",
    "be",
    "it",
    "had",
    "has",
    "have",
    "than",
    "their",
    "there",
    "about",
}


class HashEmbedder:
    """Token-overlap embedding used in tests and when the local model cannot load."""

    name = "hash"
    dims = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(text) for text in texts]


def _hash_vector(text: str) -> list[float]:
    vector = [0.0] * HashEmbedder.dims
    for token in TOKEN.findall(text.lower()):
        if token in STOPWORDS or len(token) < 3:
            continue
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:2], "big") % HashEmbedder.dims
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class FastEmbedder:
    name = "BAAI/bge-small-en-v1.5"

    def __init__(self, cache_dir: str) -> None:
        os.environ.setdefault("FASTEMBED_CACHE_PATH", cache_dir)
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.name, cache_dir=cache_dir)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


@lru_cache
def get_embedder(cache_dir: str) -> HashEmbedder | FastEmbedder:
    try:
        return FastEmbedder(cache_dir)
    except Exception:
        return HashEmbedder()
