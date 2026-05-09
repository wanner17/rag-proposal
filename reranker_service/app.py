from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from FlagEmbedding import FlagReranker
import logging

logger = logging.getLogger(__name__)

reranker: FlagReranker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global reranker
    logger.info("BGE-Reranker-v2-m3 로딩 중...")
    reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
    logger.info("BGE-Reranker 로딩 완료")
    yield
    reranker = None


app = FastAPI(lifespan=lifespan)


class RerankRequest(BaseModel):
    query: str
    passages: list[str]
    top_n: int = 5


class RerankResult(BaseModel):
    text: str
    score: float
    original_index: int


class RerankResponse(BaseModel):
    results: list[RerankResult]


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": reranker is not None}


@app.post("/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest):
    if reranker is None:
        raise HTTPException(status_code=503, detail="모델 로딩 중")
    if not req.passages:
        raise HTTPException(status_code=400, detail="passages가 비어있음")

    pairs = [[req.query, p] for p in req.passages]
    scores = reranker.compute_score(pairs, normalize=True)

    indexed = sorted(
        enumerate(zip(scores, req.passages)),
        key=lambda x: x[1][0],
        reverse=True,
    )

    results = [
        RerankResult(text=passage, score=float(score), original_index=idx)
        for idx, (score, passage) in indexed[: req.top_n]
    ]
    return RerankResponse(results=results)
