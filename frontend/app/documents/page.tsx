"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  DocumentSearchHit,
  DocumentSearchResponse,
  DocumentSummary,
  deleteDocument,
  listDocuments,
  searchDocuments,
} from "@/lib/api";
import { listProjects } from "@/lib/projects";

type Status = "loading" | "idle" | "searching" | "error";

function DocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlug = searchParams.get("project");
  const [projectId, setProjectId] = useState<string | undefined>(undefined);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [status, setStatus] = useState<Status>("loading");
  const [data, setData] = useState<DocumentSearchResponse>({ found: false, documents: [], hits: [] });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    const load = async () => {
      let resolvedProjectId: string | undefined;
      if (projectSlug) {
        const projects = await listProjects(token);
        resolvedProjectId = projects.find((p) => p.slug === projectSlug)?.id;
        setProjectId(resolvedProjectId);
      }
      const response = await listDocuments(token, resolvedProjectId);
      setData(response);
      setStatus("idle");
    };

    load().catch((err) => {
      setError(err instanceof Error ? err.message : "문서 목록 조회 중 오류가 발생했습니다.");
      setStatus("error");
    });
  }, [router, projectSlug]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || status === "searching") return;
    setStatus("searching");
    setError("");

    try {
      const token = localStorage.getItem("token") ?? "";
      const response = await searchDocuments({ query: query.trim(), top_k: clamp(topK, 1, 50), project_id: projectId }, token);
      setData(response);
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "문서 검색 중 오류가 발생했습니다.");
      setStatus("error");
    }
  }

  async function refreshDocuments() {
    const token = localStorage.getItem("token") ?? "";
    const response = await listDocuments(token, projectId);
    setData(response);
  }

  async function handleDelete(file: string) {
    const confirmed = window.confirm(
      `"${file}" 문서를 삭제할까요?\n검색 인덱스와 업로드 원본 파일이 함께 제거됩니다.`
    );
    if (!confirmed) return;

    setError("");
    setNotice("");
    try {
      const token = localStorage.getItem("token") ?? "";
      const response = await deleteDocument(file, token, projectId);
      setNotice(response.message);
      await refreshDocuments();
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "문서 삭제 중 오류가 발생했습니다.");
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen max-w-6xl mx-auto px-6 py-6">
      <header className="flex items-center justify-between mb-6 bg-white border shadow-sm rounded-2xl px-5 py-4">
        <div>
          <h1 className="text-xl font-bold text-blue-700">
            문서{projectSlug ? ` — ${projectSlug}` : ""}
          </h1>
          <p className="text-sm text-gray-500 mt-1">업로드된 문서 목록과 검색 결과 원문 조각을 확인합니다.</p>
        </div>
      </header>

      <section className="bg-white border rounded-2xl shadow-sm p-5 mb-6">
        <form onSubmit={handleSearch} className="flex flex-col gap-3 md:flex-row">
          <input
            className="flex-1 border rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            placeholder="업로드 문서에서 검색할 키워드나 질문을 입력하세요..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-gray-600">
            검색 결과 수
            <input
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(clamp(Number(e.target.value), 1, 50))}
              className="w-20 border rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </label>
          <button
            type="submit"
            disabled={!query.trim() || status === "searching"}
            className="bg-blue-600 text-white px-5 py-2.5 rounded-xl hover:bg-blue-700 disabled:opacity-40 transition text-sm font-medium"
          >
            {status === "searching" ? "검색 중..." : "검색"}
          </button>
        </form>
        <p className="text-xs text-gray-500 mt-2">LLM 요약 없이 검색된 원문 조각과 출처만 표시합니다.</p>
      </section>

      {status === "loading" && <EmptyState title="문서 목록을 불러오는 중입니다..." />}
      {status === "error" && <ErrorState message={error} />}
      {notice && (
        <section className="bg-green-50 border border-green-200 rounded-2xl shadow-sm p-4 mb-6 text-sm text-green-800">
          {notice}
        </section>
      )}

      {status !== "loading" && status !== "error" && (
        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <section className="bg-white border rounded-2xl shadow-sm p-5 h-fit">
            <h2 className="font-semibold mb-3">문서 목록</h2>
            {data.documents.length === 0 ? (
              <p className="text-sm text-gray-500">조회 가능한 업로드 문서가 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {data.documents.map((doc) => (
                  <DocumentCard key={doc.file} document={doc} onDelete={handleDelete} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="font-semibold">검색 결과</h2>
            {!query.trim() && <EmptyState title="검색어를 입력하면 업로드 문서 원문 조각이 표시됩니다." />}
            {query.trim() && data.hits.length === 0 && <EmptyState title="검색 결과가 없습니다." />}
            {data.hits.map((hit) => (
              <SearchHitCard key={hit.point_id} hit={hit} />
            ))}
          </section>
        </div>
      )}
    </div>
  );
}

function DocumentCard({
  document,
  onDelete,
}: {
  document: DocumentSummary;
  onDelete: (file: string) => void;
}) {
  return (
    <article className="border rounded-xl p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-medium text-blue-800 break-all">{document.file}</h3>
        <button
          type="button"
          onClick={() => onDelete(document.file)}
          className="shrink-0 rounded-lg border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
        >
          제거
        </button>
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {document.department || "부서 없음"} · {document.year || "연도 없음"} · {document.chunk_count} chunks
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {document.client || "발주처 없음"} / {document.domain || "도메인 없음"} / {document.project_type || "사업유형 없음"}
      </p>
      {document.pages.length > 0 && (
        <p className="text-xs text-gray-400 mt-1">pages: {document.pages.slice(0, 8).join(", ")}</p>
      )}
    </article>
  );
}

function SearchHitCard({ hit }: { hit: DocumentSearchHit }) {
  return (
    <article className="bg-white border rounded-2xl shadow-sm p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h3 className="font-semibold text-blue-800 break-all">{hit.file}</h3>
        <span className="text-xs rounded-full bg-blue-100 text-blue-800 px-2.5 py-1">
          retrieval {hit.score == null ? "N/A" : hit.score.toFixed(3)}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        p.{hit.page} {hit.section && `· ${hit.section}`} {hit.department && `· ${hit.department}`}
      </p>
      <p className="whitespace-pre-wrap text-sm leading-6 text-gray-800 bg-gray-50 border rounded-xl p-4">
        {hit.text}
      </p>
    </article>
  );
}

function EmptyState({ title }: { title: string }) {
  return (
    <section className="bg-white border rounded-2xl shadow-sm p-8 text-center text-gray-500">
      <p>{title}</p>
    </section>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <section className="bg-white border border-red-200 rounded-2xl shadow-sm p-6">
      <h2 className="font-semibold text-red-600 mb-2">오류</h2>
      <p className="text-sm text-gray-700 whitespace-pre-wrap">{message}</p>
    </section>
  );
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

export default function DocumentsPageWrapper() {
  return (
    <Suspense fallback={null}>
      <DocumentsPage />
    </Suspense>
  );
}
