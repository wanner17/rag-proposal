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
    <div className="group rounded-xl border border-gray-200 bg-white p-4 text-sm shadow-sm transition-all hover:border-blue-300 hover:shadow-md">
      <div className="flex items-center justify-between mb-2 gap-3">
        <span className="min-w-0 truncate font-semibold text-gray-900 transition-colors group-hover:text-blue-700">
          [{index + 1}] {title}
        </span>
        <span className="inline-flex shrink-0 items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
          {scoreLabel}
        </span>
      </div>
      <div className="text-xs text-gray-500">{detail}</div>
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
