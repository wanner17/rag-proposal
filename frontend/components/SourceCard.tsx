import { Source } from "@/lib/api";

export default function SourceCard({ source, index }: { source: Source; index: number }) {
  const scoreLabel = formatScore(source);
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-blue-800">[{index + 1}] {source.file}</span>
        <span className="text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full">
          {scoreLabel}
        </span>
      </div>
      <div className="text-gray-600 text-xs">
        <span>p.{source.page}</span>
        {source.section && <span className="ml-2">· {source.section}</span>}
        {source.department && <span className="ml-2">· {source.department}</span>}
      </div>
    </div>
  );
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
