from __future__ import annotations

from dataclasses import dataclass

_FRONTEND_LIB_MARKERS = [
    "jquery", "bootstrap", "kendo", "jqgrid", "videojs",
    "plupload", "htmlarea", "ckeditor", "tinymce", "summernote",
    "ext.js", "dojo", "bower_components", "node_modules",
]

_CONTAMINATION_THRESHOLD = 0.3  # >30% contaminated chunks → retry


@dataclass
class ContaminationResult:
    contaminated_count: int
    total_count: int
    contamination_ratio: float
    is_contaminated: bool
    contaminated_paths: list[str]


def detect_contamination(chunks: list[dict]) -> ContaminationResult:
    if not chunks:
        return ContaminationResult(0, 0, 0.0, False, [])

    contaminated_paths: list[str] = []
    for chunk in chunks:
        path = (chunk.get("relative_path") or chunk.get("file") or "").lower()
        if any(marker in path for marker in _FRONTEND_LIB_MARKERS):
            contaminated_paths.append(path)

    total = len(chunks)
    n_contaminated = len(contaminated_paths)
    ratio = n_contaminated / total

    return ContaminationResult(
        contaminated_count=n_contaminated,
        total_count=total,
        contamination_ratio=ratio,
        is_contaminated=ratio > _CONTAMINATION_THRESHOLD,
        contaminated_paths=list(set(contaminated_paths)),
    )
