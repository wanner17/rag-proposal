from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
import logging

logger = logging.getLogger(__name__)

model: SentenceTransformer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info("BGE-M3 모델 로딩 중...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    logger.info(f"BGE-M3 로딩 완료 (device: {device})")
    yield
    model = None


app = FastAPI(lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimension: int


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="모델 로딩 중")
    if not req.texts:
        raise HTTPException(status_code=400, detail="texts가 비어있음")

    embeddings = model.encode(
        req.texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return EmbedResponse(
        embeddings=embeddings.tolist(),
        dimension=embeddings.shape[1],
    )
