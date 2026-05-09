import { Source } from "@/lib/api";

export default function SourceCard({ source, index }: { source: Source; index: number }) {
  const confidence = Math.round(source.score * 100);
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-blue-800">[{index + 1}] {source.file}</span>
        <span className="text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full">
          {confidence}%
        </span>
      </div>
      <div className="text-gray-600 text-xs">
        <span>p.{source.page}</span>
        {source.section && <span className="ml-2">· {source.section}</span>}
      </div>
    </div>
  );
}
