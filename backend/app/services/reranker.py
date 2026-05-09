import httpx
from app.core.config import settings


async def rerank(query: str, passages: list[str], top_n: int = 5) -> list[dict]:
    if not passages:
        return []
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.RERANKER_HOST}/rerank",
            json={"query": query, "passages": passages, "top_n": top_n},
        )
        resp.raise_for_status()
        return resp.json()["results"]
