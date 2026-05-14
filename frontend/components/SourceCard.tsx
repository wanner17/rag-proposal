import { Source } from "@/lib/api";

export default function SourceCard({ source, index }: { source: Source; index: number }) {
  const scoreLabel = formatScore(source);
  const isSourceCode = source.source_kind === "source_code";
  const title = isSourceCode ? source.relative_path ?? "source file" : source.file;
  const detail = isSourceCode
    ? [
        source.language,
        formatLineRange(source.start_line, source.end_line),
        source.project_slug,
      ]
        .filter(Boolean)
        .join(" · ")
    : [
        `p.${source.page}`,
        source.section,
        source.department,
      ]
        .filter(Boolean)
        .join(" · ");

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
      <div className="flex items-center justify-between mb-1">
        <span className="min-w-0 truncate font-medium text-blue-800">
          [{index + 1}] {title}
        </span>
        <span className="ml-3 shrink-0 rounded-full bg-blue-200 px-2 py-0.5 text-xs text-blue-800">
          {scoreLabel}
        </span>
      </div>
      <div className="text-xs text-gray-600">{detail}</div>
    </div>
  );
}

function formatLineRange(startLine?: number | null, endLine?: number | null) {
  if (startLine == null || endLine == null) return "";
  return `L${startLine}-${endLine}`;
}

function formatScore(source: Source) {
  if (source.score_source === "rerank" && source.rerank_score != null) {
    return `rerank ${formatNumber(source.rerank_score)}`;
  }
  if (source.score_source === "retrieval" && source.retrieval_score != null) {
    return `retrieval ${formatNumber(source.retrieval_score)}`;
  }
  if (source.score_source === "unavailable" || source.score == null) {
    return "score unavailable";
  }
  return `score ${formatNumber(source.score)}`;
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}
