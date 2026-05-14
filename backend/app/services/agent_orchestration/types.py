from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.models.schemas import Source
from app.services.retrieval_critic import CriticResult


@dataclass(frozen=True)
class AgentWorkflowInput:
    query: str
    department: str | None
    project_id: str
    project_slug: str
    collection_name: str
    top_k: int
    top_n: int
    retrieval_scope: Literal["documents", "source_code"] = "documents"


@dataclass
class AgentWorkflowTraceStep:
    name: str
    status: str = "ok"
    duration_ms: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerQualityFinding:
    category: str
    severity: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerQualityReport:
    status: str
    findings: list[AnswerQualityFinding] = field(default_factory=list)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    evidence_sufficiency: dict[str, Any] = field(default_factory=dict)
    revision_recommended: bool = False
    revision_triggered: bool = False
    revision_count: int = 0


@dataclass
class AgentWorkflowResult:
    answer: str
    sources: list[Source]
    found: bool
    graph_run_id: str
    framework: str = "langgraph"
    graph_version: str = "agent-query-v1"
    selected_pass: str | None = None
    retry_triggered: bool = False
    fallback_used: bool = False
    steps: list[AgentWorkflowTraceStep] = field(default_factory=list)
    critic_result: CriticResult | None = None
    answer_quality: AnswerQualityReport | None = None
