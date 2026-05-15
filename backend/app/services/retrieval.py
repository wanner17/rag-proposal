from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector, Filter, FieldCondition, MatchValue,
    Prefetch, FusionQuery, Fusion, FilterSelector, PayloadSchemaType,
)
from kiwipiepy import Kiwi
from typing import Literal

from app.core.config import settings
from app.services.embedding import get_embedding
from app.services.reranker import rerank
from app.services.retrieval_critic import (
    CriticPass,
    CriticResult,
    assess_retrieval,
    build_retry_plan,
    select_best_pass,
)

kiwi = Kiwi()
_client: AsyncQdrantClient | None = None

VECTOR_DIM = 1024  # BGE-M3 출력 차원


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_HOST)
    return _client


_PAYLOAD_INDEX_FIELDS = ("chunk_type", "project_slug", "language", "source_kind")


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

    for field_name in _PAYLOAD_INDEX_FIELDS:
        try:
            await client.create_payload_index(
                collection_name=target_collection,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # index already exists


def _bm25_encode(text: str) -> SparseVector:
    # kiwipiepy 형태소 분석 기반 BM25 sparse 벡터
    tokens = kiwi.tokenize(text[:30_000])
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
    from app.services.embedding import get_embeddings
    # 256개 초과 시 나눠서 요청
    _EMBED_BATCH = 256
    dense_vecs = []
    for i in range(0, len(texts), _EMBED_BATCH):
        dense_vecs.extend(await get_embeddings(texts[i : i + _EMBED_BATCH]))

    points = []
    for chunk, dense in zip(chunks, dense_vecs):
        sparse = _bm25_encode(chunk["text"])
        points.append(PointStruct(
            id=chunk["chunk_id"],
            vector={"dense": dense, "bm25": sparse},
            payload={k: v for k, v in chunk.items() if k != "chunk_id"},
        ))

    await client.upsert(collection_name=target_collection, points=points)


RetrievalScope = Literal["documents", "source_code", "code_only"]


def _department_filter(department: str | None) -> Filter | None:
    if not department:
        return None
    return Filter(
        must=[FieldCondition(key="department", match=MatchValue(value=department))]
    )


def _source_filter(project_slug: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="source_kind", match=MatchValue(value="source_code")),
            FieldCondition(key="project_slug", match=MatchValue(value=project_slug)),
        ]
    )


def _code_only_filter() -> Filter:
    return Filter(
        must=[FieldCondition(key="source_kind", match=MatchValue(value="source_code"))]
    )


def _source_file_filter(project_slug: str, relative_path: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="source_kind", match=MatchValue(value="source_code")),
            FieldCondition(key="project_slug", match=MatchValue(value=project_slug)),
            FieldCondition(key="relative_path", match=MatchValue(value=relative_path)),
        ]
    )


def _retrieval_filter(
    department: str | None,
    retrieval_scope: RetrievalScope = "documents",
    project_slug: str | None = None,
) -> Filter | None:
    if retrieval_scope == "source_code":
        if not project_slug:
            raise ValueError("project_slug is required for source_code retrieval")
        return _source_filter(project_slug)
    if retrieval_scope == "code_only":
        return _code_only_filter()
    must = []
    if project_slug:
        must.append(FieldCondition(key="project_slug", match=MatchValue(value=project_slug)))
    if department:
        must.append(FieldCondition(key="department", match=MatchValue(value=department)))
    return Filter(must=must) if must else None


def _document_filter(file_name: str, department: str | None, project_slug: str | None = None) -> Filter:
    must = [FieldCondition(key="file", match=MatchValue(value=file_name))]
    if department:
        must.append(FieldCondition(key="department", match=MatchValue(value=department)))
    if project_slug:
        must.append(FieldCondition(key="project_slug", match=MatchValue(value=project_slug)))
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


async def fetch_project_summary_chunks(
    project_slug: str,
    collection_name: str | None = None,
) -> list[dict]:
    client = get_client()
    coll = collection_name or settings.QDRANT_COLLECTION
    points, _ = await client.scroll(
        collection_name=coll,
        scroll_filter=Filter(must=[
            FieldCondition(key="project_slug", match=MatchValue(value=project_slug)),
            FieldCondition(key="chunk_type", match=MatchValue(value="project_summary")),
        ]),
        limit=3,
        with_payload=True,
        with_vectors=False,
    )
    return [_point_to_chunk(p) for p in points]


async def hybrid_search(
    query: str,
    department: str | None,
    top_k: int = 20,
    collection_name: str | None = None,
    retrieval_scope: RetrievalScope = "documents",
    project_slug: str | None = None,
) -> list[dict]:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    dense_vec = await get_embedding(query)
    sparse_vec = _bm25_encode(query)

    query_filter = _retrieval_filter(department, retrieval_scope, project_slug)

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
    project_slug: str | None = None,
) -> list[dict]:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    must = []
    if project_slug:
        must.append(FieldCondition(key="project_slug", match=MatchValue(value=project_slug)))
    if department:
        must.append(FieldCondition(key="department", match=MatchValue(value=department)))
    scroll_filter = Filter(must=must) if must else None
    points, _ = await client.scroll(
        collection_name=target_collection,
        scroll_filter=scroll_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [_point_to_chunk(point) for point in points]


async def delete_document_chunks(
    file_name: str,
    department: str | None,
    collection_name: str | None = None,
    project_slug: str | None = None,
) -> bool:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    selector = FilterSelector(filter=_document_filter(file_name, department, project_slug))
    await client.delete(
        collection_name=target_collection,
        points_selector=selector,
        wait=True,
    )
    return True


async def delete_source_chunks(
    project_slug: str,
    relative_path: str,
    collection_name: str | None = None,
) -> bool:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    await ensure_collection(target_collection)
    selector = FilterSelector(filter=_source_file_filter(project_slug, relative_path))
    await client.delete(
        collection_name=target_collection,
        points_selector=selector,
        wait=True,
    )
    return True


async def delete_project_source_chunks(
    project_slug: str,
    collection_name: str | None = None,
) -> bool:
    client = get_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION
    await ensure_collection(target_collection)
    selector = FilterSelector(filter=_source_filter(project_slug))
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
    retrieval_scope: RetrievalScope = "documents",
    project_slug: str | None = None,
    score_threshold: float | None = None,
) -> tuple[list[dict], list[dict]]:
    if retrieval_scope == "documents" and project_slug is None:
        candidates = await hybrid_search(
            query,
            department,
            top_k=top_k,
            collection_name=collection_name,
        )
    else:
        candidates = await hybrid_search(
            query,
            department,
            top_k=top_k,
            collection_name=collection_name,
            retrieval_scope=retrieval_scope,
            project_slug=project_slug,
        )
    if not candidates:
        return [], []
    passages = [c["text"] for c in candidates]
    reranked = await rerank(query, passages, top_n=top_n, score_threshold=score_threshold)
    return candidates, merge_rerank_scores(candidates, reranked)


async def retrieve_with_critic(
    query: str,
    department: str | None,
    top_k: int = 20,
    top_n: int = 5,
    collection_name: str | None = None,
    retrieval_scope: RetrievalScope = "documents",
    project_slug: str | None = None,
    score_threshold: float | None = None,
) -> CriticResult:
    if retrieval_scope == "documents" and project_slug is None:
        initial_candidates, initial_reranked = await retrieve_with_metadata(
            query,
            department,
            top_k=top_k,
            top_n=top_n,
            collection_name=collection_name,
            score_threshold=score_threshold,
        )
    else:
        initial_candidates, initial_reranked = await retrieve_with_metadata(
            query,
            department,
            top_k=top_k,
            top_n=top_n,
            collection_name=collection_name,
            retrieval_scope=retrieval_scope,
            project_slug=project_slug,
            score_threshold=score_threshold,
        )
    initial_decision = assess_retrieval(
        query,
        initial_reranked,
        requested_top_n=top_n,
        retry_triggered=False,
        selected_pass="initial",
    )
    initial_pass = CriticPass(
        name="initial",
        candidates=initial_candidates,
        reranked=initial_reranked,
        decision=initial_decision,
    )
    if initial_decision.sufficient:
        return CriticResult(selected=initial_pass, initial=initial_pass)

    retry_plan = build_retry_plan(top_k, top_n, initial_decision.trigger_reasons)
    if retrieval_scope == "documents" and project_slug is None:
        retry_candidates, retry_reranked = await retrieve_with_metadata(
            query,
            department,
            top_k=retry_plan.top_k,
            top_n=retry_plan.top_n,
            collection_name=collection_name,
            score_threshold=score_threshold,
        )
    else:
        retry_candidates, retry_reranked = await retrieve_with_metadata(
            query,
            department,
            top_k=retry_plan.top_k,
            top_n=retry_plan.top_n,
            collection_name=collection_name,
            retrieval_scope=retrieval_scope,
            project_slug=project_slug,
            score_threshold=score_threshold,
        )
    retry_decision = assess_retrieval(
        query,
        retry_reranked,
        requested_top_n=retry_plan.top_n,
        retry_triggered=True,
        selected_pass="retry",
    )
    retry_pass = CriticPass(
        name="retry",
        candidates=retry_candidates,
        reranked=retry_reranked,
        decision=retry_decision,
    )
    selected = select_best_pass(initial_pass, retry_pass)
    return CriticResult(selected=selected, initial=initial_pass, retry=retry_pass)


async def retrieve(
    query: str,
    department: str | None,
    top_n: int = 5,
    collection_name: str | None = None,
    retrieval_scope: RetrievalScope = "documents",
    project_slug: str | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    critic_result = await retrieve_with_critic(
        query,
        department,
        top_k=20,
        top_n=top_n,
        collection_name=collection_name,
        retrieval_scope=retrieval_scope,
        project_slug=project_slug,
        score_threshold=score_threshold,
    )
    return critic_result.selected.reranked
