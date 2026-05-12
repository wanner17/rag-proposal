from typing import Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    file: str
    page: int = 0
    year: int
    client: str
    domain: str
    project_type: str
    department: str
    section: str = ""


class ChunkPayload(DocumentMetadata):
    text: str
    chunk_id: str


class IngestRequest(BaseModel):
    year: int
    client: str
    domain: str
    project_type: str
    department: str


class Source(BaseModel):
    file: str
    page: int
    section: str
    score: float


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    department: Optional[str] = None   # None이면 권한 내 전체 검색


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    found: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    user_id: str
    username: str
    department: str
    is_admin: bool = False


class DocumentSummary(BaseModel):
    file: str
    department: str | None = None
    year: int | None = None
    client: str | None = None
    domain: str | None = None
    project_type: str | None = None
    pages: list[int] = []
    sections: list[str] = []
    chunk_count: int = 0


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=50)


class DocumentSearchHit(BaseModel):
    point_id: str
    file: str
    page: int = 0
    section: str = ""
    department: str | None = None
    score: float | None = None
    score_source: str = "retrieval"
    text: str


class DocumentSearchResponse(BaseModel):
    found: bool
    documents: list[DocumentSummary]
    hits: list[DocumentSearchHit]


class DocumentDeleteResponse(BaseModel):
    deleted: bool
    file: str
    indexed_chunks_deleted: bool
    source_file_deleted: bool
    message: str
