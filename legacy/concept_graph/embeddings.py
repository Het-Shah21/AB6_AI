import logging
from typing import Any

from src.llm.provider import get_embedding_model

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> list[float]:
    model = await get_embedding_model()
    result = await model.aembed_query(text)
    return result


async def generate_embeddings_batch(
    texts: list[str],
) -> list[list[float]]:
    model = await get_embedding_model()
    results = await model.aembed_documents(texts)
    return results


def cosine_similarity(a: list[float], b: list[float]) -> float:
    import numpy as np
    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
    dot = float(np.dot(a_arr, b_arr))
    norm_a = float(np.linalg.norm(a_arr))
    norm_b = float(np.linalg.norm(b_arr))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
