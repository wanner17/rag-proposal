"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import SourceCard from "@/components/SourceCard";
import {
  draftProposal,
  ProposalDraftResponse,
  ProposalSource,
  ProposalVariant,
} from "@/plugins/proposal/api";

type Status = "idle" | "loading" | "success" | "no_results" | "error";

type DraftSection = {
  title: string;
  body: string;
};

const WORKFLOW_STEPS = [
  { title: "요청 정리", description: "작성 목적과 범위 확인" },
  { title: "근거 검색", description: "관련 문서 조각 탐색" },
  { title: "근거 선별", description: "초안에 쓸 출처 압축" },
  { title: "초안 생성", description: "섹션별 문단 구성" },
  { title: "검토 준비", description: "출처와 경고 확인" },
];

export default function ProposalsPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(12);
  const [topN, setTopN] = useState(5);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ProposalDraftResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("token")) router.push("/login");
  }, [router]);

  const activeVariant = useMemo(() => result?.variants?.[0] ?? null, [result]);

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
          scenario_id: null,
          query: query.trim(),
          department: null,
          top_k: safeTopK,
          top_n: safeTopN,
        },
        token
      );
      setResult(response);
      if (response.status === "error") {
        setError(response.warnings.join("\n") || "제안서 초안 생성 중 오류가 발생했습니다.");
        setStatus("error");
      } else {
        setStatus(response.found ? "success" : "no_results");
      }
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
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-6">
        <header className="mb-6 overflow-hidden rounded-3xl border bg-white shadow-sm">
          <div className="bg-gradient-to-r from-blue-700 via-blue-600 to-cyan-500 px-6 py-6 text-white">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-blue-100">Proposal Draft Dashboard</p>
                <h1 className="mt-1 text-2xl font-bold">제안서 초안 생성</h1>
                <p className="mt-2 max-w-2xl text-sm text-blue-50">
                  요청, 근거 검색, 초안, 출처 검토를 한 화면에서 확인합니다.
                </p>
              </div>
              <nav className="flex flex-wrap gap-3 text-sm">
                <a href="/chat" className="rounded-full bg-white/15 px-3 py-1.5 text-white hover:bg-white/25">채팅</a>
                <a href="/documents" className="rounded-full bg-white/15 px-3 py-1.5 text-white hover:bg-white/25">문서 조회</a>
                <a href="/upload" className="rounded-full bg-white/15 px-3 py-1.5 text-white hover:bg-white/25">문서 업로드</a>
                <button onClick={handleLogout} className="rounded-full bg-white px-3 py-1.5 text-blue-700 hover:bg-blue-50">로그아웃</button>
              </nav>
            </div>
          </div>
          <WorkflowStepper status={status} />
        </header>

        <div className="grid gap-6 lg:grid-cols-[390px_1fr]">
          <aside className="space-y-4">
            <section className="rounded-3xl border bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">초안 요청</h2>
                  <p className="mt-1 text-xs text-gray-500">작성할 제안서 상황과 섹션을 입력하세요.</p>
                </div>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">입력</span>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">프롬프트</label>
                  <textarea
                    className="min-h-40 w-full rounded-2xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="예: 공공기관 클라우드 전환 제안서의 추진전략, 보안/DR, 단계별 이행계획 초안을 작성해줘."
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <NumberField label="넓게 찾을 문서 조각 수" value={topK} min={1} max={50} onChange={setTopK} />
                  <NumberField label="초안에 사용할 근거 수" value={topN} min={1} max={10} onChange={setTopN} />
                </div>

                <button
                  type="submit"
                  disabled={status === "loading" || !query.trim()}
                  className="w-full rounded-2xl bg-blue-600 py-3 font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
                >
                  {status === "loading" ? "초안 생성 중..." : "초안 생성"}
                </button>
              </form>
            </section>

            <InsightPanel topK={topK} topN={topN} status={status} />
          </aside>

          <main className="space-y-5">
            {status === "idle" && <DashboardEmptyState />}

            {status === "loading" && <LoadingDashboard />}

            {status === "error" && (
              <section className="rounded-3xl border border-red-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-medium text-red-500">생성 실패</p>
                <h2 className="mt-1 text-lg font-semibold text-red-700">오류가 발생했습니다</h2>
                <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">{error}</p>
              </section>
            )}

            {status === "no_results" && result && (
              <section className="rounded-3xl border bg-white p-6 shadow-sm">
                <p className="text-sm font-medium text-amber-600">검색 결과 없음</p>
                <h2 className="mt-1 text-lg font-semibold">근거 문서를 찾지 못했습니다</h2>
                <p className="mt-3 text-sm text-gray-700">
                  {result.no_results_message || "관련 제안서 근거 문서를 찾지 못했습니다."}
                </p>
                <Warnings warnings={result.warnings} />
              </section>
            )}

            {status === "success" && result && activeVariant && (
              <>
                <DashboardSummary result={result} variant={activeVariant} />
                <VariantSection variant={activeVariant} primary />
                {result.variants.slice(1).map((variant) => (
                  <VariantSection key={variant.variant_id} variant={variant} />
                ))}
                <EvidenceDashboard sources={result.shared_sources} title="공통 출처 대시보드" />
              </>
            )}
          </main>
        </div>
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
      <span className="mb-1 block">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(clamp(Number(e.target.value), min, max))}
        className="w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </label>
  );
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function WorkflowStepper({ status }: { status: Status }) {
  const activeIndex = status === "idle" ? 0 : status === "loading" ? 2 : status === "error" ? 3 : 4;
  const isFinished = status === "success" || status === "no_results";

  return (
    <div className="grid gap-3 px-5 py-4 md:grid-cols-5">
      {WORKFLOW_STEPS.map((step, index) => {
        const complete = isFinished || index < activeIndex;
        const active = !isFinished && index === activeIndex;
        return (
          <div
            key={step.title}
            className={`rounded-2xl border p-3 transition ${
              complete
                ? "border-blue-200 bg-blue-50"
                : active
                  ? "border-cyan-300 bg-cyan-50 shadow-sm"
                  : "border-gray-200 bg-gray-50"
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  complete
                    ? "bg-blue-600 text-white"
                    : active
                      ? "bg-cyan-500 text-white"
                      : "bg-gray-200 text-gray-500"
                }`}
              >
                {complete ? "✓" : index + 1}
              </span>
              <p className="text-sm font-semibold text-gray-900">{step.title}</p>
            </div>
            <p className="mt-2 text-xs text-gray-500">{step.description}</p>
          </div>
        );
      })}
    </div>
  );
}

function InsightPanel({ topK, topN, status }: { topK: number; topN: number; status: Status }) {
  return (
    <section className="rounded-3xl border bg-white p-5 shadow-sm">
      <h2 className="font-semibold">생성 설정 해석</h2>
      <div className="mt-4 space-y-3 text-sm">
        <SettingMeter label="검색 범위" value={topK} max={50} help={`${topK}개 문서 조각을 넓게 찾습니다.`} />
        <SettingMeter label="초안 근거" value={topN} max={10} help={`${topN}개 근거를 초안 작성에 사용합니다.`} />
      </div>
      <div className="mt-4 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-gray-600">
        {status === "loading"
          ? "현재 입력값으로 관련 근거를 찾고 초안을 구성하는 중입니다. 실제 백엔드 진행률이 아닌 화면용 단계 표시입니다."
          : "검색 범위는 넓게 볼 후보 수, 초안 근거는 최종 초안에 반영할 출처 수입니다."}
      </div>
    </section>
  );
}

function SettingMeter({ label, value, max, help }: { label: string; value: number; max: number; help: string }) {
  const percent = Math.max(4, Math.min(100, (value / max) * 100));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-xs text-gray-500">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-100">
        <div className="h-full rounded-full bg-blue-500" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1 text-xs text-gray-500">{help}</p>
    </div>
  );
}

function DashboardEmptyState() {
  return (
    <section className="rounded-3xl border bg-white p-8 shadow-sm">
      <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr]">
        <div>
          <p className="text-sm font-medium text-blue-600">시작 대기</p>
          <h2 className="mt-2 text-2xl font-bold text-gray-900">요청을 입력하면 대시보드가 채워집니다</h2>
          <p className="mt-3 text-sm leading-6 text-gray-600">
            생성 후에는 초안 섹션, 근거 출처, 품질 신호, 경고를 한 화면에서 검토할 수 있습니다.
          </p>
        </div>
        <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-cyan-50 p-5">
          <p className="text-sm font-semibold text-gray-800">화면 구성</p>
          <ul className="mt-3 space-y-2 text-sm text-gray-600">
            <li>• 생성 단계 흐름</li>
            <li>• 요약 메트릭 카드</li>
            <li>• 섹션별 초안 보기</li>
            <li>• 출처 검토 대시보드</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function LoadingDashboard() {
  return (
    <section className="rounded-3xl border bg-white p-8 shadow-sm">
      <div className="flex flex-col items-center justify-center text-center">
        <div className="mb-4 h-12 w-12 animate-pulse rounded-full bg-blue-100 ring-8 ring-blue-50" />
        <p className="text-sm font-medium text-blue-600">초안 생성 중</p>
        <h2 className="mt-2 text-xl font-bold">근거를 찾고 제안서 문단을 구성하고 있습니다</h2>
        <p className="mt-2 max-w-xl text-sm text-gray-500">
          검색, 근거 선별, 초안 생성이 순차적으로 진행됩니다. 완료되면 섹션별 초안과 출처 대시보드가 표시됩니다.
        </p>
      </div>
    </section>
  );
}

function DashboardSummary({ result, variant }: { result: ProposalDraftResponse; variant: ProposalVariant }) {
  const uniqueFiles = uniqueSourceFiles(result.shared_sources).length;
  const warningCount = result.warnings.length + variant.warnings.length;
  const bestScore = bestSourceScore(result.shared_sources);

  return (
    <section className="grid gap-3 md:grid-cols-4">
      <MetricCard label="생성 상태" value={statusLabel(result.status)} tone="blue" detail={`request ${shortId(result.request_id)}`} />
      <MetricCard label="근거 출처" value={`${result.shared_sources.length}개`} tone="green" detail={`${uniqueFiles}개 파일에서 확인`} />
      <MetricCard label="최고 점수" value={bestScore ? bestScore.toFixed(3) : "-"} tone="purple" detail="retrieval/rerank 기준" />
      <MetricCard label="검토 경고" value={`${warningCount}건`} tone={warningCount ? "amber" : "green"} detail="주의 메시지 확인" />
    </section>
  );
}

function MetricCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: "blue" | "green" | "purple" | "amber" }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    purple: "bg-purple-50 text-purple-700 border-purple-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
  }[tone];

  return (
    <div className={`rounded-3xl border p-4 shadow-sm ${toneClass}`}>
      <p className="text-xs font-medium opacity-80">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      <p className="mt-1 text-xs opacity-80">{detail}</p>
    </div>
  );
}

function VariantSection({ variant, primary = false }: { variant: ProposalVariant; primary?: boolean }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const sections = useMemo(() => parseDraftSections(variant.draft_markdown), [variant.draft_markdown]);

  async function copyDraft() {
    try {
      await navigator.clipboard.writeText(variant.draft_markdown);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("failed");
      window.setTimeout(() => setCopyState("idle"), 1600);
    }
  }

  return (
    <section className="rounded-3xl border bg-white shadow-sm">
      <div className="border-b px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-blue-600">{primary ? "대표 초안" : "대안 초안"}</p>
            <h2 className="mt-1 text-xl font-bold text-gray-900">{variant.title}</h2>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <Badge label={`variant ${variant.variant_id}`} />
              <Badge label={`strategy ${variant.strategy}`} />
              <Badge label={`${sections.length}개 섹션`} />
            </div>
          </div>
          <button
            type="button"
            onClick={copyDraft}
            className="rounded-full border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            {copyState === "copied" ? "복사됨" : copyState === "failed" ? "복사 실패" : "초안 복사"}
          </button>
        </div>

        {variant.quality_summary && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">품질 요약</p>
            <p className="mt-1 leading-6">{variant.quality_summary}</p>
          </div>
        )}
      </div>

      <div className="grid gap-5 p-6 xl:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          {sections.map((section, index) => (
            <article key={`${section.title}-${index}`} className="rounded-2xl border bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                  {index + 1}
                </span>
                <h3 className="font-semibold text-gray-900">{section.title}</h3>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-7 text-gray-700">{section.body}</p>
            </article>
          ))}
        </div>

        <aside className="space-y-4">
          <ReviewChecklist sectionCount={sections.length} sourceCount={variant.sources.length} warningCount={variant.warnings.length} />
          {variant.sources.length > 0 && <EvidenceMiniSummary sources={variant.sources} />}
        </aside>
      </div>

      <div className="px-6 pb-6">
        <Warnings warnings={variant.warnings} />
      </div>
    </section>
  );
}

function ReviewChecklist({ sectionCount, sourceCount, warningCount }: { sectionCount: number; sourceCount: number; warningCount: number }) {
  const checks = [
    { label: "섹션 구성", value: `${sectionCount}개`, ok: sectionCount > 1 },
    { label: "근거 연결", value: `${sourceCount}개`, ok: sourceCount > 0 },
    { label: "경고 확인", value: warningCount ? `${warningCount}건` : "없음", ok: warningCount === 0 },
  ];

  return (
    <div className="rounded-2xl border bg-white p-4">
      <h3 className="font-semibold">검토 체크</h3>
      <div className="mt-3 space-y-2">
        {checks.map((check) => (
          <div key={check.label} className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-sm">
            <span className="text-gray-600">{check.label}</span>
            <span className={check.ok ? "font-medium text-emerald-700" : "font-medium text-amber-700"}>{check.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceMiniSummary({ sources }: { sources: ProposalSource[] }) {
  return (
    <div className="rounded-2xl border bg-white p-4">
      <h3 className="font-semibold">초안 근거 요약</h3>
      <ScoreNotice />
      <div className="mt-3 space-y-2">
        {uniqueSourceFiles(sources).slice(0, 5).map((file) => (
          <div key={file} className="truncate rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-800">
            {file}
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceDashboard({ sources, title }: { sources: ProposalSource[]; title: string }) {
  const files = uniqueSourceFiles(sources);
  const bestScore = bestSourceScore(sources);
  const rerankCount = sources.filter((source) => source.score_source === "rerank").length;

  return (
    <section className="rounded-3xl border bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-blue-600">Evidence Review</p>
          <h2 className="mt-1 text-lg font-bold">{title}</h2>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge label={`${sources.length}개 출처`} />
          <Badge label={`${files.length}개 파일`} />
          <Badge label={`rerank ${rerankCount}개`} />
          <Badge label={`best ${bestScore ? bestScore.toFixed(3) : "-"}`} />
        </div>
      </div>

      <ScoreNotice />

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {files.slice(0, 6).map((file) => {
          const count = sources.filter((source) => source.file === file).length;
          return (
            <div key={file} className="rounded-2xl border bg-slate-50 p-3">
              <p className="truncate text-sm font-medium text-gray-800">{file}</p>
              <p className="mt-1 text-xs text-gray-500">연결 근거 {count}개</p>
            </div>
          );
        })}
      </div>

      <div className="mt-5 space-y-2">
        {sources.map((source, index) => (
          <SourceCard key={source.point_id || index} source={source} index={index} />
        ))}
      </div>
    </section>
  );
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings?.length) return null;
  return (
    <div className="mt-4 rounded-2xl border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
      <p className="font-medium">주의 / 경고</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {warnings.map((warning, index) => (
          <li key={index}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}

function ScoreNotice() {
  return (
    <p className="mt-2 text-xs leading-5 text-gray-500">
      점수는 출처별 score_source에 따라 retrieval 또는 rerank로 표시됩니다. 서로 다른 후보 생성 조건의 점수는 직접 비교 순위로 해석하지 마세요.
    </p>
  );
}

function Badge({ label }: { label: string }) {
  return <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700">{label}</span>;
}

function parseDraftSections(markdown: string): DraftSection[] {
  const lines = markdown.split(/\r?\n/);
  const sections: DraftSection[] = [];
  let title = "초안 본문";
  let body: string[] = [];

  for (const line of lines) {
    const nextTitle = extractSectionTitle(line);
    if (nextTitle) {
      if (body.join("\n").trim()) {
        sections.push({ title, body: body.join("\n").trim() });
      }
      title = nextTitle;
      body = [];
    } else {
      body.push(line);
    }
  }

  if (body.join("\n").trim()) {
    sections.push({ title, body: body.join("\n").trim() });
  }

  if (!sections.length && markdown.trim()) {
    return [{ title: "초안 본문", body: markdown.trim() }];
  }

  return sections;
}

function extractSectionTitle(line: string) {
  const heading = line.match(/^#{1,6}\s+(.+)$/);
  if (heading) return heading[1].trim();

  const numbered = line.match(/^\d+[.)]\s+(.{1,50})$/);
  if (numbered) return numbered[1].trim();

  return null;
}

function uniqueSourceFiles(sources: ProposalSource[]) {
  return Array.from(new Set(sources.map((source) => source.file).filter(Boolean)));
}

function bestSourceScore(sources: ProposalSource[]) {
  const scores = sources
    .map((source) => source.rerank_score ?? source.retrieval_score ?? source.score)
    .filter((score): score is number => typeof score === "number");
  return scores.length ? Math.max(...scores) : null;
}

function shortId(id: string) {
  return id ? id.slice(0, 8) : "-";
}

function statusLabel(status: string) {
  if (status === "ok") return "완료";
  if (status === "partial") return "부분 완료";
  if (status === "no_results") return "근거 없음";
  if (status === "error") return "오류";
  return status;
}
