"""
Local embedding engine using fastembed.

Model: BAAI/bge-small-en-v1.5
- 384 dimensions
- ~130 MB download, cached after first run
- Runs on CPU — fast enough on Mac Mini M4 for this workload
- No API key needed
"""
from functools import lru_cache
from typing import List

from fastembed import TextEmbedding

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model() -> TextEmbedding:
    """Load the embedding model once and cache it."""
    return TextEmbedding(model_name=EMBEDDING_MODEL)


def embed(text: str) -> List[float]:
    """Embed a single string. Returns a list of floats."""
    model = _get_model()
    vectors = list(model.embed([text]))
    return vectors[0].tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed multiple strings in one pass."""
    model = _get_model()
    return [v.tolist() for v in model.embed(texts)]
