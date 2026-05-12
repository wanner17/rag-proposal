from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


@dataclass
class AgentWorkflowTraceStep:
    name: str
    status: str = "ok"
    duration_ms: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)


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
