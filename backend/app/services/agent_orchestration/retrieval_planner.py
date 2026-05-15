from __future__ import annotations

from dataclasses import dataclass, field

from app.services.agent_orchestration.question_classifier import QuestionType


@dataclass
class RetrievalPlan:
    question_type: QuestionType
    priority_chunk_types: list[str]
    priority_paths: list[str]
    exclude_paths: list[str]
    boost_project_summary: bool
    top_k: int
    top_n: int
    score_threshold: float
    # mutable runtime fields (updated during retry)
    _extra_exclude_paths: list[str] = field(default_factory=list, repr=False)

    @property
    def effective_exclude_paths(self) -> list[str]:
        return self.exclude_paths + self._extra_exclude_paths


_FRONTEND_LIB_EXCLUDES = [
    "**/assets/**", "**/vendor/**", "**/jquery/**", "**/jquery-ui/**",
    "**/bootstrap/**", "**/kendo*/**", "**/jqgrid/**", "**/videojs/**",
    "**/plupload*/**", "**/htmlarea/**", "**/ckeditor/**", "**/tinymce/**",
    "**/summernote/**", "**/bower_components/**", "**/ext/**", "**/dwr/**",
]

_STRATEGIES: dict[QuestionType, dict] = {
    QuestionType.PROJECT_OVERVIEW: dict(
        priority_chunk_types=["project_summary", "config_file", "java_class"],
        priority_paths=[
            "**/README*", "**/pom.xml", "**/web.xml",
            "**/application*.properties", "**/*Controller*", "**/*Service*",
        ],
        exclude_paths=_FRONTEND_LIB_EXCLUDES,
        boost_project_summary=True,
        top_k=30, top_n=8, score_threshold=0.3,
    ),
    QuestionType.DB_SQL_TRACING: dict(
        priority_chunk_types=["xml_query", "java_method"],
        priority_paths=[
            "**/*Mapper*", "**/*mapper*", "**/*.sql",
            "**/*DAO*", "**/*Dao*", "**/*Repository*",
        ],
        exclude_paths=["**/assets/**", "**/vendor/**"],
        boost_project_summary=False,
        top_k=25, top_n=7, score_threshold=0.4,
    ),
    QuestionType.FEATURE_FLOW: dict(
        priority_chunk_types=["java_class", "java_method"],
        priority_paths=[
            "**/*Controller*", "**/*Service*", "**/*Handler*", "**/*Manager*",
        ],
        exclude_paths=["**/assets/**", "**/vendor/**"],
        boost_project_summary=False,
        top_k=25, top_n=7, score_threshold=0.4,
    ),
    QuestionType.UI_JSP: dict(
        priority_chunk_types=["jsp_section"],
        priority_paths=["**/*.jsp"],
        exclude_paths=_FRONTEND_LIB_EXCLUDES,
        boost_project_summary=False,
        top_k=20, top_n=5, score_threshold=0.4,
    ),
    QuestionType.DEPLOY_CONFIG: dict(
        priority_chunk_types=["config_file"],
        priority_paths=[
            "**/pom.xml", "**/web.xml", "**/application*.properties",
            "**/logback*.xml", "**/context*.xml",
        ],
        exclude_paths=["**/assets/**", "**/vendor/**"],
        boost_project_summary=False,
        top_k=15, top_n=5, score_threshold=0.35,
    ),
    QuestionType.ERROR_DEBUG: dict(
        priority_chunk_types=["java_method", "java_class"],
        priority_paths=[
            "**/*Exception*", "**/*Handler*", "**/*Filter*", "**/*Interceptor*",
        ],
        exclude_paths=["**/assets/**", "**/vendor/**"],
        boost_project_summary=False,
        top_k=25, top_n=7, score_threshold=0.35,
    ),
    QuestionType.GENERAL: dict(
        priority_chunk_types=[],
        priority_paths=[],
        exclude_paths=["**/assets/**", "**/vendor/**"],
        boost_project_summary=False,
        top_k=20, top_n=5, score_threshold=0.4,
    ),
}


def build_retrieval_plan(
    question_type: QuestionType,
    base_top_k: int | None = None,
    base_top_n: int | None = None,
) -> RetrievalPlan:
    cfg = _STRATEGIES[question_type]
    return RetrievalPlan(
        question_type=question_type,
        priority_chunk_types=list(cfg["priority_chunk_types"]),
        priority_paths=list(cfg["priority_paths"]),
        exclude_paths=list(cfg["exclude_paths"]),
        boost_project_summary=cfg["boost_project_summary"],
        top_k=base_top_k or cfg["top_k"],
        top_n=base_top_n or cfg["top_n"],
        score_threshold=cfg["score_threshold"],
    )
