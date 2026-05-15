from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    file: str
    page: int = 0
    department: str
    section: str = ""


class ChunkPayload(DocumentMetadata):
    text: str
    chunk_id: str


class DocumentSource(BaseModel):
    source_kind: Literal["document"] = "document"
    file: str
    page: int
    section: str
    score: float
    score_source: str = "retrieval"


class SourceCodeSource(BaseModel):
    source_kind: Literal["source_code"] = "source_code"
    project_slug: str
    relative_path: str
    language: str
    start_line: int
    end_line: int
    score: float
    score_source: str = "retrieval"


Source = Annotated[DocumentSource | SourceCodeSource, Field(discriminator="source_kind")]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    department: Optional[str] = None   # None이면 권한 내 전체 검색
    project_id: Optional[str] = None


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
    pages: list[int] = []
    sections: list[str] = []
    chunk_count: int = 0


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=50)
    project_id: Optional[str] = None


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
