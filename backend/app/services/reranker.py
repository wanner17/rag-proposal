import httpx
from app.core.config import settings


async def rerank(
    query: str,
    passages: list[str],
    top_n: int = 5,
    score_threshold: float | None = None,
) -> list[dict]:
    if not passages:
        return []
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.RERANKER_HOST}/rerank",
            json={"query": query, "passages": passages, "top_n": top_n},
        )
        resp.raise_for_status()
        results = resp.json()["results"]

    if score_threshold is None:
        return results

    filtered = [r for r in results if r.get("score", 0.0) >= score_threshold]
    if len(filtered) < 2:
        filtered = results[:2]
    return filtered
