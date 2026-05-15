"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getProject,
  getProjectSummary,
  updateProjectSummary,
  generateProjectSummaryDraft,
  Project,
} from "@/lib/projects";

export default function SummaryPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [token, setToken] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    void load(t);
  }, []);

  async function load(t: string) {
    try {
      const [p, summary] = await Promise.all([
        getProject(projectId, t),
        getProjectSummary(projectId, t),
      ]);
      setProject(p);
      setContent(summary.content ?? "");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "불러오기 실패");
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setStatus("");
    try {
      const { draft } = await generateProjectSummaryDraft(projectId, token);
      setContent(draft);
      setStatus("초안이 생성되었습니다. 검토 후 저장해주세요.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "생성 실패");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setStatus("");
    try {
      await updateProjectSummary(projectId, content, token);
      setStatus("저장 및 재임베딩 완료");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  if (!project) return <div className="p-8 text-gray-500">로딩 중...</div>;

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-4">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700">← 뒤로</button>
        <h1 className="text-xl font-semibold">{project.name} — 프로젝트 요약</h1>
      </div>

      <p className="text-sm text-gray-500">
        RAG_PROJECT_SUMMARY.md — 프로젝트 개요 질문에 우선 활용됩니다.
      </p>

      <textarea
        className="w-full h-96 border rounded p-3 text-sm font-mono"
        value={content}
        onChange={e => setContent(e.target.value)}
        placeholder="# 프로젝트 개요&#10;..."
      />

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-gray-100 border rounded hover:bg-gray-200 disabled:opacity-50 text-sm"
        >
          {generating ? "생성 중..." : "자동 초안 생성"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !content.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {saving ? "저장 중..." : "저장 및 재임베딩"}
        </button>
        {status && (
          <span className={`text-sm ${status.includes("실패") ? "text-red-500" : "text-green-600"}`}>
            {status}
          </span>
        )}
      </div>
    </div>
  );
}
