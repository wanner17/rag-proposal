import httpx
from functools import lru_cache
from app.core.config import settings


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.EMBEDDING_HOST}/embed",
            json={"texts": texts},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


async def get_embedding(text: str) -> list[float]:
    results = await get_embeddings([text])
    return results[0]
