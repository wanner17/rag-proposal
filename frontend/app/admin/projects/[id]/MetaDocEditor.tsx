"use client";

import { useState } from "react";
import {
  generateMetaDocDraft,
  META_DOC_LABELS,
  MetaDocType,
  saveMetaDoc,
} from "@/lib/meta_docs";

interface MetaDocEditorProps {
  projectId: string;
  docType: MetaDocType;
  initialContent: string | null;
  token: string;
}

export function MetaDocEditor({ projectId, docType, initialContent, token }: MetaDocEditorProps) {
  const [content, setContent] = useState(initialContent ?? "");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  async function handleGenerate() {
    setGenerating(true);
    setStatus("");
    try {
      const { draft } = await generateMetaDocDraft(projectId, docType, token);
      setContent(draft);
      setStatus("초안이 생성되었습니다. 검토 후 저장해주세요.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "생성 실패");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!content.trim()) return;
    setSaving(true);
    setStatus("");
    try {
      await saveMetaDoc(projectId, docType, content, token);
      setStatus("저장 및 재임베딩 완료");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  const label = META_DOC_LABELS[docType];
  const filenames: Record<MetaDocType, string> = {
    project_summary: "RAG_PROJECT_SUMMARY.md",
    menu_map: "RAG_MENU_MAP.md",
    feature_map: "RAG_FEATURE_MAP.md",
    db_schema_summary: "RAG_DB_SCHEMA_SUMMARY.md",
    architecture: "RAG_ARCHITECTURE.md",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-700">{label}</p>
          <p className="text-xs text-slate-400">{filenames[docType]} — PROJECT_OVERVIEW 질문에 우선 사용됩니다</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-3 py-1.5 text-xs font-medium bg-slate-100 border border-slate-200 rounded-lg hover:bg-slate-200 disabled:opacity-50 transition-colors"
          >
            {generating ? "생성 중..." : "자동 초안 생성"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !content.trim()}
            className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          >
            {saving ? "저장 중..." : "저장 + 재임베딩"}
          </button>
        </div>
      </div>

      <textarea
        className="w-full h-72 border border-slate-300 rounded-xl px-4 py-3 text-sm font-mono text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-y"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={`# ${label}\n\n내용을 입력하거나 자동 초안 생성 버튼을 눌러주세요.`}
      />

      {status && (
        <p className={`text-xs ${status.includes("실패") ? "text-red-500" : "text-green-600"}`}>
          {status}
        </p>
      )}
    </div>
  );
}
