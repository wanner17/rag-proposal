"use client";
import { useState, useEffect } from "react";

export interface AgentStep {
  name: string;
  index: number;
  status: "running" | "done";
  durationMs?: number;
}

const STEP_LABELS: Record<string, string> = {
  prepare_context: "컨텍스트 준비",
  retrieve_evidence: "문서 검색",
  generate_answer: "답변 생성",
  review_answer_quality: "품질 검토",
  finalize_response: "최종화",
};

export default function AgentThinkingPanel({
  steps,
  isStreaming,
}: {
  steps: AgentStep[];
  isStreaming: boolean;
}) {
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (!isStreaming && steps.length > 0) {
      setExpanded(false);
    }
  }, [isStreaming, steps.length]);

  if (steps.length === 0) return null;

  const totalMs = steps
    .filter((s) => s.status === "done" && s.durationMs != null)
    .reduce((sum, s) => sum + (s.durationMs ?? 0), 0);

  return (
    <div className="mb-2 rounded-lg border border-gray-200 bg-gray-50 text-xs">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
      >
        <div className="flex items-center gap-2 flex-wrap">
          {steps.map((step) => (
            <span key={step.index} className="flex items-center gap-1 text-gray-600">
              {step.status === "running" ? (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
              ) : (
                <span className="text-emerald-500">✓</span>
              )}
              <span>{STEP_LABELS[step.name] ?? step.name}</span>
              {step.status === "done" && step.durationMs != null && (
                <span className="text-gray-400">{(step.durationMs / 1000).toFixed(1)}s</span>
              )}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2 ml-2 shrink-0 text-gray-400">
          {!isStreaming && totalMs > 0 && (
            <span>{(totalMs / 1000).toFixed(1)}s 총</span>
          )}
          <span>{expanded ? "▲" : "▼"}</span>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-gray-200 px-3 py-2 space-y-1">
          {steps.map((step) => (
            <div key={step.index} className="flex items-center gap-2 text-gray-500">
              <span className="w-4 text-center">
                {step.status === "running" ? (
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
                ) : (
                  <span className="text-emerald-500">✓</span>
                )}
              </span>
              <span className="font-medium text-gray-700">{STEP_LABELS[step.name] ?? step.name}</span>
              {step.status === "done" && step.durationMs != null && (
                <span className="text-gray-400">{step.durationMs.toFixed(0)}ms</span>
              )}
              {step.status === "running" && (
                <span className="text-blue-400">실행 중...</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
