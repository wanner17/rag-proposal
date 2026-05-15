"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getProject, Project } from "@/lib/projects";
import {
  getAllMetaDocs,
  AllMetaDocsResponse,
  META_DOC_LABELS,
  META_DOC_TYPES,
  MetaDocType,
} from "@/lib/meta_docs";
import { MetaDocEditor } from "./MetaDocEditor";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [token, setToken] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [metaDocs, setMetaDocs] = useState<AllMetaDocsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<MetaDocType>("project_summary");
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    void load(t);
  }, []);

  async function load(t: string) {
    try {
      const [p, docs] = await Promise.all([
        getProject(projectId, t),
        getAllMetaDocs(projectId, t),
      ]);
      setProject(p);
      setMetaDocs(docs);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "불러오기 실패");
    }
  }

  if (loadError) {
    return (
      <div className="p-8">
        <p className="text-red-500">{loadError}</p>
        <button onClick={() => router.back()} className="mt-4 text-sm text-slate-500 hover:underline">← 뒤로</button>
      </div>
    );
  }

  if (!project || !metaDocs) {
    return <div className="p-8 text-slate-400 text-sm">불러오는 중...</div>;
  }

  const activeDoc = metaDocs[activeTab];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <header className="mb-6 flex items-center gap-4">
          <button
            onClick={() => router.push("/admin/projects")}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            ← 프로젝트 목록
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
            <p className="text-sm text-slate-500">{project.slug}</p>
          </div>
        </header>

        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-6">
            <h2 className="text-lg font-bold text-slate-900">프로젝트 메타 문서</h2>
            <p className="mt-1 text-sm text-slate-500">
              각 문서는 &quot;이 사이트는 무슨 사이트야?&quot; 같은 개요 질문에 우선적으로 활용됩니다.
              자동 초안 생성 후 수정하여 저장하면 즉시 재임베딩됩니다.
            </p>
          </div>

          {/* Tab navigation */}
          <div className="flex gap-1 border-b border-slate-100 px-6 pt-4">
            {META_DOC_TYPES.map((docType) => {
              const exists = metaDocs[docType].exists;
              return (
                <button
                  key={docType}
                  onClick={() => setActiveTab(docType)}
                  className={`relative px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                    activeTab === docType
                      ? "bg-white border border-b-white border-slate-200 text-indigo-600 -mb-px z-10"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {META_DOC_LABELS[docType]}
                  {exists && (
                    <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Editor */}
          <div className="p-6">
            <MetaDocEditor
              key={activeTab}
              projectId={projectId}
              docType={activeTab}
              initialContent={activeDoc.content}
              token={token}
            />
          </div>
        </div>

        {/* Quick links */}
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <a href={`/admin/projects/${projectId}/summary`} className="text-slate-400 hover:text-slate-600 underline-offset-2 hover:underline">
            구 요약 편집
          </a>
          <a href={`/admin/projects/${projectId}/debug`} className="text-slate-400 hover:text-slate-600 underline-offset-2 hover:underline">
            검색 디버그
          </a>
          <a href={`/admin/projects/${projectId}/exclusions`} className="text-slate-400 hover:text-slate-600 underline-offset-2 hover:underline">
            제외 규칙
          </a>
        </div>
      </div>
    </div>
  );
}
