from typing import Literal

from pydantic import BaseModel, Field


class ProposalDraftRequest(BaseModel):
    query: str | None = Field(default=None, max_length=2000)
    scenario_id: str | None = None
    department: str | None = None
    top_k: int = Field(default=20, ge=1, le=50)
    top_n: int = Field(default=5, ge=1, le=10)


class ProposalSource(BaseModel):
    point_id: str
    file: str
    page: int = 0
    section: str = ""
    score: float | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None
    score_source: str
    department: str | None = None


class ProposalVariant(BaseModel):
    variant_id: str
    title: str
    strategy: str
    draft_markdown: str
    sources: list[ProposalSource]
    warnings: list[str] = []
    quality_summary: str | None = None


class ProposalDraftResponse(BaseModel):
    request_id: str
    found: bool
    status: Literal["ok", "no_results", "partial", "error"]
    scenario_id: str | None = None
    department_scope: str | None = None
    variants: list[ProposalVariant]
    shared_sources: list[ProposalSource]
    warnings: list[str] = []
    no_results_message: str | None = None
