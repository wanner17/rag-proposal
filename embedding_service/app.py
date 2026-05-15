from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import json
import torch
import logging
import re
import unicodedata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model: SentenceTransformer | None = None

MAX_TEXT_LENGTH = 8000
MAX_TEXTS_PER_REQUEST = 64
MAX_BATCH_SIZE = 16


def sanitize_text(text: str) -> str:
    # null 바이트 제거
    text = text.replace("\x00", " ")
    # 제어문자 제거 (탭·개행 제외)
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    # 유효하지 않은 유니코드 대체문자 제거
    text = "".join(c for c in text if unicodedata.category(c) != "Cs")
    # 연속 공백 압축
    text = re.sub(r" {2,}", " ", text).strip()
    return text


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
    if len(req.texts) > MAX_TEXTS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"texts 개수 초과 (최대 {MAX_TEXTS_PER_REQUEST}개)",
        )

    cleaned = []
    truncated_count = 0
    for i, text in enumerate(req.texts):
        if not isinstance(text, str):
            raise HTTPException(status_code=400, detail=f"texts[{i}] 문자열 아님")
        text = sanitize_text(text)
        if not text:
            text = " "  # 빈 텍스트는 공백으로 대체 (encode 오류 방지)
        if len(text) > MAX_TEXT_LENGTH:
            truncated_count += 1
            text = text[:MAX_TEXT_LENGTH]
        cleaned.append(text)

    if truncated_count:
        logger.warning(json.dumps({
            "event": "texts_truncated",
            "count": truncated_count,
            "max_length": MAX_TEXT_LENGTH,
        }))

    logger.info(json.dumps({
        "event": "embed_request",
        "batch_size": len(cleaned),
        "max_len": max(len(t) for t in cleaned),
        "truncated_count": truncated_count,
    }))

    try:
        embeddings = model.encode(
            cleaned,
            normalize_embeddings=True,
            batch_size=MAX_BATCH_SIZE,
            show_progress_bar=False,
        )
    except Exception as e:
        logger.exception("임베딩 실패")
        raise HTTPException(status_code=500, detail=f"임베딩 실패: {e}")

    return EmbedResponse(
        embeddings=embeddings.tolist(),
        dimension=embeddings.shape[1],
    )
