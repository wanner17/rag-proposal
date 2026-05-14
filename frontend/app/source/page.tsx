"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  listProjects,
  triggerCheckout,
  getCheckoutStatus,
  triggerReindex,
  triggerIncrementalIndex,
  getSourceIndexStatus,
  type Project,
  type CheckoutStatus,
  type SourceIndexStatus,
} from "@/lib/projects";

type IndexingPhase = "idle" | "running" | "done" | "error";

function SourcePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlug = searchParams.get("project");

  const [project, setProject] = useState<Project | null>(null);
  const [loadError, setLoadError] = useState("");

  const [checkoutState, setCheckoutState] = useState<CheckoutStatus>({
    status: "idle", message: "", progress: 0,
  });
  const [indexStatus, setIndexStatus] = useState<SourceIndexStatus | null>(null);
  const [indexingPhase, setIndexingPhase] = useState<IndexingPhase>("idle");
  const [actionError, setActionError] = useState("");

  const checkoutPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const indexPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const token = () => localStorage.getItem("token") ?? "";

  // 프로젝트 로드
  useEffect(() => {
    if (!projectSlug) { router.push("/projects"); return; }
    const t = token();
    if (!t) { router.push("/login"); return; }

    listProjects(t)
      .then((list) => {
        const found = list.find((p) => p.slug === projectSlug);
        if (!found) { setLoadError("프로젝트를 찾을 수 없습니다."); return; }
        setProject(found);
        // 초기 색인 상태 조회
        getSourceIndexStatus(found.id, t)
          .then(setIndexStatus)
          .catch(() => {});
        // 초기 체크아웃 상태 조회
        getCheckoutStatus(found.id, t)
          .then(setCheckoutState)
          .catch(() => {});
      })
      .catch(() => router.push("/login"));
  }, [projectSlug, router]);

  // 체크아웃 폴링
  const startCheckoutPoll = useCallback((projectId: string) => {
    if (checkoutPollRef.current) return;
    checkoutPollRef.current = setInterval(async () => {
      try {
        const s = await getCheckoutStatus(projectId, token());
        setCheckoutState(s);
        if (s.status === "done" || s.status === "error") {
          clearInterval(checkoutPollRef.current!);
          checkoutPollRef.current = null;
          // 완료 후 색인 상태 갱신
          getSourceIndexStatus(projectId, token()).then(setIndexStatus).catch(() => {});
        }
      } catch { /* ignore */ }
    }, 2000);
  }, []);

  // 색인 폴링
  const startIndexPoll = useCallback((projectId: string) => {
    if (indexPollRef.current) return;
    indexPollRef.current = setInterval(async () => {
      try {
        const s = await getSourceIndexStatus(projectId, token());
        setIndexStatus(s);
        if (s.status !== "indexing") {
          clearInterval(indexPollRef.current!);
          indexPollRef.current = null;
          setIndexingPhase(s.status === "ready" ? "done" : "error");
        }
      } catch { /* ignore */ }
    }, 2000);
  }, []);

  useEffect(() => () => {
    if (checkoutPollRef.current) clearInterval(checkoutPollRef.current);
    if (indexPollRef.current) clearInterval(indexPollRef.current);
  }, []);

  async function handleCheckout() {
    if (!project) return;
    setActionError("");
    try {
      const s = await triggerCheckout(project.id, token());
      setCheckoutState(s);
      startCheckoutPoll(project.id);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "오류가 발생했습니다.");
    }
  }

  async function handleReindex() {
    if (!project) return;
    setActionError("");
    setIndexingPhase("running");
    try {
      await triggerReindex(project.id, token());
      startIndexPoll(project.id);
    } catch (e: unknown) {
      setIndexingPhase("error");
      setActionError(e instanceof Error ? e.message : "오류가 발생했습니다.");
    }
  }

  async function handleIncremental() {
    if (!project) return;
    setActionError("");
    setIndexingPhase("running");
    try {
      await triggerIncrementalIndex(project.id, token());
      startIndexPoll(project.id);
    } catch (e: unknown) {
      setIndexingPhase("error");
      setActionError(e instanceof Error ? e.message : "오류가 발생했습니다.");
    }
  }

  if (loadError) return <ErrorMessage message={loadError} />;
  if (!project) return <Loading />;

  const config = project.source_config;
  const checkoutRunning = checkoutState.status === "running";
  const indexRunning = indexingPhase === "running" || indexStatus?.status === "indexing";
  const checkoutDone = checkoutState.status === "done";
  const hasCheckedOut = checkoutDone || (indexStatus && indexStatus.status !== "never_indexed");

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8 border-b border-gray-200 pb-5">
        <p className="text-sm text-gray-500">사내 RAG 플랫폼</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900">소스코드 관리</h1>
        <div className="mt-2 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4">
          <p className="text-base font-medium text-gray-700">{project.name}</p>
          {config?.svn_url && (
            <p className="text-sm text-gray-500 font-mono bg-gray-100 px-2 py-0.5 rounded-md break-all">{config.svn_url}</p>
          )}
        </div>
      </header>

      {actionError && (
        <div className="mb-6 rounded-md bg-red-50 p-4 shadow-sm ring-1 ring-inset ring-red-200">
          <p className="text-sm font-medium text-red-800">{actionError}</p>
        </div>
      )}

      {/* 1단계: 저장소 내려받기 */}
      <section className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">1단계</span>
          {checkoutState.status === "done" && <StatusBadge status="done" />}
          {checkoutState.status === "error" && <StatusBadge status="error" />}
          {checkoutState.status === "running" && <StatusBadge status="running" />}
        </div>
        <h2 className="text-lg font-semibold leading-7 text-gray-900 mb-1">저장소 내려받기</h2>
        <p className="text-sm text-gray-500 mb-6">
          서버에 소스코드를 가져옵니다.
        </p>

        {checkoutState.status === "running" && (
          <ProgressBar progress={checkoutState.progress} message={checkoutState.message} />
        )}

        <button
          onClick={handleCheckout}
          disabled={checkoutRunning}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:bg-blue-400 transition-colors"
        >
          {checkoutRunning ? "⏳ 내려받는 중..." : "📥 저장소 내려받기"}
        </button>

        {!config?.svn_url && (
          <p className="mt-4 text-sm text-amber-600 bg-amber-50 p-3 rounded-md ring-1 ring-inset ring-amber-200/50">
            저장소 주소(SVN URL)가 설정되지 않았습니다.{" "}
            <a href="/admin/projects" className="font-semibold underline hover:text-amber-800">프로젝트 관리</a>에서 설정하세요.
          </p>
        )}
      </section>

      {/* 2단계: AI 분석 준비 */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">2단계</span>
          {indexStatus?.status === "ready" && <StatusBadge status="done" label="색인 완료" />}
          {indexStatus?.status === "indexing" && <StatusBadge status="running" label="색인 중" />}
          {indexStatus?.status === "failed" && <StatusBadge status="error" />}
        </div>
        <h2 className="text-lg font-semibold leading-7 text-gray-900 mb-1">AI 분석 준비 (임베딩)</h2>
        <p className="text-sm text-gray-500 mb-6">
          소스코드를 AI가 검색할 수 있도록 분석합니다.
        </p>

        {indexStatus && (
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3 bg-gray-50 p-4 rounded-lg border border-gray-100 text-sm">
            <div>
              <p className="text-gray-500 mb-1 text-xs">색인된 파일</p>
              <p className="font-semibold text-gray-900">{indexStatus.counts?.indexed ?? 0}개</p>
            </div>
            {indexStatus.last_successful_revision && (
              <div>
                <p className="text-gray-500 mb-1 text-xs">마지막 리비전</p>
                <p className="font-semibold text-gray-900 font-mono">r{indexStatus.last_successful_revision}</p>
              </div>
            )}
            {indexStatus.last_full_indexed_at && (
              <div>
                <p className="text-gray-500 mb-1 text-xs">전체 분석 일시</p>
                <p className="font-semibold text-gray-900">{new Date(indexStatus.last_full_indexed_at).toLocaleString("ko-KR")}</p>
              </div>
            )}
          </div>
        )}

        {indexRunning && (
          <div className="mb-6">
            <ProgressBar progress={-1} message="분석 중..." />
          </div>
        )}

        <div className="flex gap-3 flex-wrap">
          <button
            onClick={handleReindex}
            disabled={indexRunning}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:bg-blue-400 transition-colors"
          >
            {indexRunning ? "⏳ 분석 중..." : "🔍 전체 분석 시작"}
          </button>
          {hasCheckedOut && (
            <button
              onClick={handleIncremental}
              disabled={indexRunning}
              className="inline-flex items-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              🔄 변경분만 업데이트
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

function ProgressBar({ progress, message }: { progress: number; message: string }) {
  return (
    <div className="mb-4">
      <p className="text-xs text-gray-500 mb-1">{message}</p>
      <div className="w-full bg-gray-100 rounded-full h-2">
        {progress >= 0 ? (
          <div
            className="bg-blue-500 h-2 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        ) : (
          <div className="bg-blue-400 h-2 rounded-full animate-pulse w-full" />
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status, label }: { status: "done" | "running" | "error"; label?: string }) {
  const map = {
    done: "bg-green-50 text-green-700 ring-green-600/20",
    running: "bg-blue-50 text-blue-700 ring-blue-700/10",
    error: "bg-red-50 text-red-700 ring-red-600/10",
  };
  const defaultLabel = { done: "완료", running: "진행 중", error: "오류" };
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${map[status]}`}>
      {label ?? defaultLabel[status]}
    </span>
  );
}

function Loading() {
  return <div className="p-8 text-sm text-gray-400">불러오는 중...</div>;
}

function ErrorMessage({ message }: { message: string }) {
  return <div className="p-8 text-sm text-red-500">{message}</div>;
}

export default function SourcePageWrapper() {
  return (
    <Suspense fallback={<Loading />}>
      <SourcePage />
    </Suspense>
  );
}
