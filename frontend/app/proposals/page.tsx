"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import SourceCard from "@/components/SourceCard";
import {
  draftProposal,
  ProposalDraftResponse,
  ProposalVariant,
} from "@/lib/api";

const SCENARIOS = [
  {
    id: "demo-public-si-modernization",
    label: "공공 SI 고도화",
    query: "교육청 노후 업무시스템 고도화 사업 제안서의 추진전략, 구현방안, 일정/리스크 섹션 초안을 작성해줘.",
  },
  {
    id: "demo-learning-platform",
    label: "LMS 플랫폼",
    query: "공공기관 이러닝 플랫폼 구축 제안서의 사업 이해, 제안 접근방안, 운영 지원 방안을 초안으로 작성해줘.",
  },
  {
    id: "demo-smart-factory-ai",
    label: "제조 AI PoC",
    query: "제조 설비 예측정비 AI PoC 제안서 초안을 작성하고 데이터 수집, 모델 운영, 현장 적용 리스크를 정리해줘.",
  },
  {
    id: "demo-public-cloud-migration",
    label: "공공 클라우드",
    query: "공공기관 클라우드 전환 사업 제안서의 전환 전략, 보안/DR, 비용 최적화, 단계별 이행계획 초안을 작성해줘.",
  },
  {
    id: "demo-healthcare-scope-check",
    label: "헬스케어 범위",
    query: "병원 데이터 플랫폼 제안서의 개인정보 보호, 데이터 거버넌스, 분석 포털 구축 방안을 초안으로 작성해줘.",
  },
];

type Status = "idle" | "loading" | "success" | "no_results" | "error";

export default function ProposalsPage() {
  const router = useRouter();
  const [query, setQuery] = useState(SCENARIOS[0].query);
  const [scenarioId, setScenarioId] = useState<string | null>(SCENARIOS[0].id);
  const [department, setDepartment] = useState("");
  const [topK, setTopK] = useState(12);
  const [topN, setTopN] = useState(5);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ProposalDraftResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("token")) router.push("/login");
  }, [router]);

  const activeVariant = useMemo(() => result?.variants?.[0] ?? null, [result]);

  function chooseScenario(id: string, scenarioQuery: string) {
    setScenarioId(id);
    setQuery(scenarioQuery);
    setResult(null);
    setStatus("idle");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || status === "loading") return;

    setStatus("loading");
    setResult(null);
    setError("");

    try {
      const token = localStorage.getItem("token") ?? "";
      const safeTopK = clamp(topK, 1, 50);
      const safeTopN = clamp(topN, 1, 10);
      const response = await draftProposal(
        {
          scenario_id: scenarioId,
          query: query.trim(),
          department: department.trim() || null,
          top_k: safeTopK,
          top_n: safeTopN,
        },
        token
      );
      setResult(response);
      setStatus(response.found ? "success" : "no_results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "제안서 초안 생성 중 오류가 발생했습니다.");
      setStatus("error");
    }
  }

  function handleLogout() {
    localStorage.removeItem("token");
    router.push("/login");
  }

  return (
    <div className="min-h-screen max-w-6xl mx-auto px-6 py-6">
      <header className="flex items-center justify-between mb-6 bg-white border shadow-sm rounded-2xl px-5 py-4">
        <div>
          <h1 className="text-xl font-bold text-blue-700">제안서 초안 생성</h1>
          <p className="text-sm text-gray-500 mt-1">근거 문서와 검색 품질 신호를 함께 확인합니다.</p>
        </div>
        <nav className="flex gap-3 text-sm">
          <a href="/chat" className="text-gray-500 hover:text-gray-700">채팅</a>
          <a href="/upload" className="text-gray-500 hover:text-gray-700">문서 업로드</a>
          <button onClick={handleLogout} className="text-red-500 hover:text-red-700">로그아웃</button>
        </nav>
      </header>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <aside className="bg-white border rounded-2xl shadow-sm p-5 h-fit">
          <h2 className="font-semibold mb-3">초안 요청</h2>
          <div className="grid grid-cols-2 gap-2 mb-4">
            {SCENARIOS.map((scenario) => (
              <button
                key={scenario.id}
                type="button"
                onClick={() => chooseScenario(scenario.id, scenario.query)}
                className={`rounded-xl border px-3 py-2 text-sm text-left transition ${
                  scenarioId === scenario.id
                    ? "border-blue-500 bg-blue-50 text-blue-700"
                    : "border-gray-200 hover:border-blue-300"
                }`}
              >
                {scenario.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">프롬프트 / 시나리오</label>
              <textarea
                className="w-full min-h-36 border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setScenarioId(null);
                }}
                placeholder="작성할 제안서 섹션이나 상황을 입력하세요."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">부서 범위 (선택)</label>
              <input
                className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="예: 공공사업팀"
              />
              <p className="text-xs text-gray-400 mt-1">권한이 제한된 사용자는 서버에서 허용 부서로 좁혀집니다.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <NumberField label="검색 후보 top_k" value={topK} min={1} max={50} onChange={setTopK} />
              <NumberField label="초안 근거 top_n" value={topN} min={1} max={10} onChange={setTopN} />
            </div>

            <button
              type="submit"
              disabled={status === "loading" || !query.trim()}
              className="w-full bg-blue-600 text-white rounded-xl py-2.5 font-medium hover:bg-blue-700 disabled:opacity-40 transition"
            >
              {status === "loading" ? "초안 생성 중..." : "초안 생성"}
            </button>
          </form>
        </aside>

        <main className="space-y-5">
          {status === "idle" && (
            <EmptyState title="시나리오를 선택하거나 직접 요청을 입력하세요." />
          )}

          {status === "loading" && (
            <EmptyState title="근거 문서를 검색하고 제안서 초안을 생성하고 있습니다..." />
          )}

          {status === "error" && (
            <section className="bg-white border border-red-200 rounded-2xl shadow-sm p-6">
              <h2 className="font-semibold text-red-600 mb-2">오류</h2>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{error}</p>
            </section>
          )}

          {status === "no_results" && result && (
            <section className="bg-white border rounded-2xl shadow-sm p-6">
              <h2 className="font-semibold mb-2">검색 결과 없음</h2>
              <p className="text-sm text-gray-700">
                {result.no_results_message || "관련 제안서 근거 문서를 찾지 못했습니다."}
              </p>
              <Warnings warnings={result.warnings} />
            </section>
          )}

          {status === "success" && result && activeVariant && (
            <>
              <ResultMeta result={result} />
              <VariantSection variant={activeVariant} primary />
              {result.variants.slice(1).map((variant) => (
                <VariantSection key={variant.variant_id} variant={variant} />
              ))}
              <section className="bg-white border rounded-2xl shadow-sm p-6">
                <h2 className="font-semibold mb-3">공통 출처</h2>
                <ScoreNotice />
                <div className="space-y-2 mt-3">
                  {result.shared_sources.map((source, index) => (
                    <SourceCard key={source.point_id || index} source={source} index={index} />
                  ))}
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-sm font-medium text-gray-700">
      <span className="block mb-1">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(clamp(Number(e.target.value), min, max))}
        className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </label>
  );
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function EmptyState({ title }: { title: string }) {
  return (
    <section className="bg-white border rounded-2xl shadow-sm p-10 text-center text-gray-500">
      <p>{title}</p>
    </section>
  );
}

function ResultMeta({ result }: { result: ProposalDraftResponse }) {
  return (
    <section className="bg-white border rounded-2xl shadow-sm p-5">
      <div className="flex flex-wrap gap-2 text-xs text-gray-600">
        <Badge label={`request ${result.request_id}`} />
        <Badge label={`status ${result.status}`} />
        <Badge label={`scenario ${result.scenario_id || "custom"}`} />
        <Badge label={`department ${result.department_scope || "all/allowed"}`} />
      </div>
      <Warnings warnings={result.warnings} />
    </section>
  );
}

function VariantSection({ variant, primary = false }: { variant: ProposalVariant; primary?: boolean }) {
  return (
    <section className="bg-white border rounded-2xl shadow-sm p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-xs text-blue-600 font-medium">{primary ? "대표 초안" : "대안 초안"}</p>
          <h2 className="text-lg font-bold">{variant.title}</h2>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge label={`variant ${variant.variant_id}`} />
          <Badge label={`strategy ${variant.strategy}`} />
        </div>
      </div>

      {variant.quality_summary && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-900 mb-4">
          <p className="font-medium mb-1">품질 요약</p>
          <p>{variant.quality_summary}</p>
        </div>
      )}

      <article className="prose prose-sm max-w-none bg-gray-50 border rounded-xl p-4 whitespace-pre-wrap text-sm leading-6">
        {variant.draft_markdown}
      </article>

      <Warnings warnings={variant.warnings} />

      {variant.sources.length > 0 && (
        <div className="mt-5">
          <h3 className="font-semibold mb-2">초안 근거 출처</h3>
          <ScoreNotice />
          <div className="space-y-2 mt-3">
            {variant.sources.map((source, index) => (
              <SourceCard key={source.point_id || index} source={source} index={index} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings?.length) return null;
  return (
    <div className="mt-4 rounded-xl border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
      <p className="font-medium mb-1">주의 / 경고</p>
      <ul className="list-disc pl-5 space-y-1">
        {warnings.map((warning, index) => (
          <li key={index}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}

function ScoreNotice() {
  return (
    <p className="text-xs text-gray-500">
      점수는 출처별 score_source에 따라 retrieval 또는 rerank로 표시됩니다. 서로 다른 후보 생성 조건의 점수는 직접 비교 순위로 해석하지 마세요.
    </p>
  );
}

function Badge({ label }: { label: string }) {
  return <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700">{label}</span>;
}
