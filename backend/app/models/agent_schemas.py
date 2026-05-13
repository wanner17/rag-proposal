from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import Source


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    project_id: str | None = None
    department: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    top_n: int | None = Field(default=None, ge=1, le=10)


class AgentWorkflowStep(BaseModel):
    name: str
    status: str = "ok"
    duration_ms: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentAnswerQualityFinding(BaseModel):
    category: str
    severity: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentAnswerQualityReport(BaseModel):
    status: str
    findings: list[AgentAnswerQualityFinding] = Field(default_factory=list)
    coverage: list[dict[str, Any]] = Field(default_factory=list)
    evidence_sufficiency: dict[str, Any] = Field(default_factory=dict)
    revision_recommended: bool = False
    revision_triggered: bool = False
    revision_count: int = 0


class AgentWorkflowMetadata(BaseModel):
    framework: str
    graph_version: str
    graph_run_id: str
    project_id: str
    project_slug: str
    collection_name: str
    selected_pass: str | None = None
    retry_triggered: bool = False
    fallback_used: bool = False
    steps: list[AgentWorkflowStep] = Field(default_factory=list)
    answer_quality: AgentAnswerQualityReport | None = None


class AgentQueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    found: bool
    metadata: AgentWorkflowMetadata
