from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector, Filter, FieldCondition, MatchValue,
    Prefetch, FusionQuery, Fusion, FilterSelector,
)
from kiwipiepy import Kiwi
from app.core.config import settings
from app.services.embedding import get_embedding
from app.services.reranker import rerank

kiwi = Kiwi()
_client: AsyncQdrantClient | None = None

VECTOR_DIM = 1024  # BGE-M3 출력 차원


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_HOST)
    return _client


async def ensure_collection(collection_name: str | None = None):
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if target_collection not in names:
        await client.create_collection(
            collection_name=target_collection,
            vectors_config={"dense": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)},
            sparse_vectors_config={
                "bm25": SparseVectorParams(index=SparseIndexParams(on_disk=False))
            },
        )


def _bm25_encode(text: str) -> SparseVector:
    # kiwipiepy 형태소 분석 기반 BM25 sparse 벡터
    tokens = kiwi.tokenize(text)
    token_texts = [t.form for t in tokens if t.tag not in ("SF", "SP", "SS")]
    freq: dict[int, float] = {}
    for token in token_texts:
        idx = hash(token) % 30000  # 간단한 해시 인덱싱
        freq[idx] = freq.get(idx, 0) + 1.0
    if not freq:
        return SparseVector(indices=[0], values=[0.0])
    return SparseVector(indices=list(freq.keys()), values=list(freq.values()))


async def index_chunks(chunks: list[dict], collection_name: str | None = None):
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    await ensure_collection(target_collection)

    texts = [c["text"] for c in chunks]
    dense_vecs = []
    # 배치 처리 (임베딩 서비스 한 번에 요청)
    from app.services.embedding import get_embeddings
    dense_vecs = await get_embeddings(texts)

    points = []
    for chunk, dense in zip(chunks, dense_vecs):
        sparse = _bm25_encode(chunk["text"])
        points.append(PointStruct(
            id=chunk["chunk_id"],
            vector={"dense": dense, "bm25": sparse},
            payload={k: v for k, v in chunk.items() if k != "chunk_id"},
        ))

    await client.upsert(collection_name=target_collection, points=points)


def _department_filter(department: str | None) -> Filter | None:
    if not department:
        return None
    return Filter(
        must=[FieldCondition(key="department", match=MatchValue(value=department))]
    )


def _document_filter(file_name: str, department: str | None) -> Filter:
    must = [FieldCondition(key="file", match=MatchValue(value=file_name))]
    if department:
        must.append(FieldCondition(key="department", match=MatchValue(value=department)))
    return Filter(must=must)


def _point_to_chunk(point) -> dict:
    payload = dict(point.payload or {})
    point_id = getattr(point, "id", None)
    retrieval_score = getattr(point, "score", None)
    payload["point_id"] = str(point_id) if point_id is not None else payload.get("chunk_id", "")
    payload["retrieval_score"] = retrieval_score
    payload.setdefault("score", retrieval_score)
    payload["score_source"] = "retrieval"
    return payload


async def hybrid_search(
    query: str,
    department: str | None,
    top_k: int = 20,
    collection_name: str | None = None,
) -> list[dict]:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    dense_vec = await get_embedding(query)
    sparse_vec = _bm25_encode(query)

    query_filter = _department_filter(department)

    results = await client.query_points(
        collection_name=target_collection,
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=top_k),
            Prefetch(query=sparse_vec, using="bm25", limit=top_k),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )
    return [_point_to_chunk(r) for r in results.points]


async def list_indexed_chunks(
    department: str | None,
    limit: int = 500,
    collection_name: str | None = None,
) -> list[dict]:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    points, _ = await client.scroll(
        collection_name=target_collection,
        scroll_filter=_department_filter(department),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [_point_to_chunk(point) for point in points]


async def delete_document_chunks(
    file_name: str,
    department: str | None,
    collection_name: str | None = None,
) -> bool:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    selector = FilterSelector(filter=_document_filter(file_name, department))
    await client.delete(
        collection_name=target_collection,
        points_selector=selector,
        wait=True,
    )
    return True


def merge_rerank_scores(candidates: list[dict], reranked: list[dict]) -> list[dict]:
    """Merge reranker output into candidates without losing retrieval metadata."""
    result = []
    for r in reranked:
        orig_idx = r["original_index"]
        chunk = dict(candidates[orig_idx])
        rerank_score = r.get("score")
        chunk["rerank_score"] = rerank_score
        chunk["score"] = rerank_score
        chunk["score_source"] = "rerank"
        result.append(chunk)
    return result


async def retrieve_with_metadata(
    query: str,
    department: str | None,
    top_k: int = 20,
    top_n: int = 5,
    collection_name: str | None = None,
) -> tuple[list[dict], list[dict]]:
    candidates = await hybrid_search(
        query,
        department,
        top_k=top_k,
        collection_name=collection_name,
    )
    if not candidates:
        return [], []
    passages = [c["text"] for c in candidates]
    reranked = await rerank(query, passages, top_n=top_n)
    return candidates, merge_rerank_scores(candidates, reranked)


async def retrieve(
    query: str,
    department: str | None,
    top_n: int = 5,
    collection_name: str | None = None,
) -> list[dict]:
    _, reranked = await retrieve_with_metadata(
        query,
        department,
        top_k=20,
        top_n=top_n,
        collection_name=collection_name,
    )
    return reranked
