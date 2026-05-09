from pydantic import BaseModel, Field
from typing import Optional


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
