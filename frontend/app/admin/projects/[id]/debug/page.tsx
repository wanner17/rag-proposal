"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getProject, Project } from "@/lib/projects";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

interface DebugChunk {
  relative_path?: string;
  file?: string;
  chunk_type?: string;
  language?: string;
  start_line?: number;
  end_line?: number;
  score?: number;
  text?: string;
  class_name?: string;
  method_name?: string;
}

interface TraceStep {
  name: string;
  duration_ms: number;
  detail: Record<string, unknown>;
}

interface DebugResult {
  answer: string;
  found: boolean;
  sources: unknown[];
  steps: TraceStep[];
  chunks?: DebugChunk[];
  question_type?: string;
  retry_count?: number;
}

export default function DebugPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [token, setToken] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<DebugResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    getProject(projectId, t).then(setProject).catch(() => {});
  }, []);

  async function runDebug() {
    if (!query.trim() || !project) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          query,
          project_id: projectId,
          retrieval_scope: "source_code",
          top_k: 20,
          top_n: 5,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패");
    } finally {
      setRunning(false);
    }
  }

  if (!project) return <div className="p-8 text-gray-500">로딩 중...</div>;

  const classifyStep = result?.steps?.find(s => s.name === "classify_question");
  const validateStep = result?.steps?.find(s => s.name === "validate_retrieval");
  const replanSteps = result?.steps?.filter(s => s.name === "replan_retrieval") ?? [];

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700">← 뒤로</button>
        <h1 className="text-xl font-semibold">{project.name} — 검색 디버그</h1>
      </div>

      {/* Query input */}
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          placeholder="질문을 입력하세요..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && runDebug()}
        />
        <button
          onClick={runDebug}
          disabled={running || !query.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {running ? "실행 중..." : "실행"}
        </button>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {result && (
        <div className="space-y-4">
          {/* Classification & validation summary */}
          <div className="bg-gray-50 border rounded p-4 text-sm space-y-1">
            {classifyStep && (
              <p><span className="font-medium">질문 유형:</span> {String(classifyStep.detail.question_type ?? "—")}</p>
            )}
            {validateStep && (
              <>
                <p><span className="font-medium">오염 비율:</span> {String(validateStep.detail.contamination_ratio ?? "—")}</p>
                <p><span className="font-medium">이슈:</span> {JSON.stringify(validateStep.detail.issues ?? [])}</p>
                <p><span className="font-medium">재시도:</span> {String(validateStep.detail.should_retry ?? false)}</p>
              </>
            )}
            {replanSteps.length > 0 && (
              <p className="text-orange-600"><span className="font-medium">리플랜 횟수:</span> {replanSteps.length}</p>
            )}
          </div>

          {/* Workflow trace */}
          <div>
            <h2 className="font-medium mb-2 text-sm">워크플로우 단계</h2>
            <div className="space-y-1">
              {result.steps.map((step, i) => (
                <div key={i} className="flex items-start gap-2 text-xs font-mono border-l-2 border-gray-200 pl-3 py-1">
                  <span className="text-gray-500 w-6">{i + 1}.</span>
                  <span className="font-semibold w-40 shrink-0">{step.name}</span>
                  <span className="text-gray-400 w-16 shrink-0">{step.duration_ms}ms</span>
                  <span className="text-gray-600 truncate">{JSON.stringify(step.detail)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Retrieved sources */}
          {Array.isArray(result.sources) && result.sources.length > 0 && (
            <div>
              <h2 className="font-medium mb-2 text-sm">검색된 소스 ({result.sources.length}개)</h2>
              <div className="space-y-1">
                {(result.sources as DebugChunk[]).map((src, i) => (
                  <div key={i} className="text-xs font-mono bg-gray-50 border rounded px-3 py-2 flex items-center gap-3">
                    <span className="text-gray-400 w-4">{i + 1}</span>
                    <span className="text-blue-700 truncate flex-1">
                      {src.relative_path ?? src.file ?? "—"}
                    </span>
                    <span className="text-purple-600">{src.chunk_type ?? "—"}</span>
                    <span className="text-green-600">{src.score != null ? src.score.toFixed(3) : "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Answer preview */}
          <div>
            <h2 className="font-medium mb-2 text-sm">생성된 답변</h2>
            <div className="border rounded p-4 text-sm whitespace-pre-wrap bg-white max-h-64 overflow-y-auto">
              {result.answer || <span className="text-gray-400">결과 없음</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
