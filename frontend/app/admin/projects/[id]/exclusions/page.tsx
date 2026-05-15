"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getProject, updateProject, Project } from "@/lib/projects";

const PRESET_EXCLUDES = [
  "**/jquery/**", "**/jquery-ui/**", "**/bootstrap/**", "**/kendo*/**",
  "**/jqgrid/**", "**/videojs/**", "**/plupload*/**", "**/htmlarea/**",
  "**/ckeditor/**", "**/tinymce/**", "**/summernote/**",
  "**/bower_components/**", "**/ext/**", "**/dwr/**",
];

export default function ExclusionsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [token, setToken] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [includes, setIncludes] = useState("");
  const [excludes, setExcludes] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    void load(t);
  }, []);

  async function load(t: string) {
    try {
      const p = await getProject(projectId, t);
      setProject(p);
      setIncludes((p.source_config.include_globs ?? []).join("\n"));
      setExcludes((p.source_config.exclude_globs ?? []).join("\n"));
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "불러오기 실패");
    }
  }

  function addPresets() {
    const current = new Set(excludes.split("\n").map(s => s.trim()).filter(Boolean));
    PRESET_EXCLUDES.forEach(p => current.add(p));
    setExcludes([...current].join("\n"));
  }

  async function save() {
    if (!project) return;
    setSaving(true);
    setStatus("");
    try {
      await updateProject(projectId, {
        source_config: {
          ...project.source_config,
          include_globs: includes.split("\n").map(s => s.trim()).filter(Boolean),
          exclude_globs: excludes.split("\n").map(s => s.trim()).filter(Boolean),
        },
      }, token);
      setStatus("저장 완료");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  if (!project) return <div className="p-8 text-gray-500">로딩 중...</div>;

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700">← 뒤로</button>
        <h1 className="text-xl font-semibold">{project.name} — 제외 규칙</h1>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">포함 glob (한 줄에 하나)</label>
        <textarea
          className="w-full h-40 border rounded p-2 text-sm font-mono"
          value={includes}
          onChange={e => setIncludes(e.target.value)}
          placeholder="**/*.java&#10;**/*.xml&#10;**/*.sql"
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-gray-700">제외 glob (한 줄에 하나)</label>
          <button
            onClick={addPresets}
            className="text-xs px-3 py-1 bg-yellow-100 border border-yellow-300 rounded hover:bg-yellow-200"
          >
            + 라이브러리 프리셋 추가 (kendo/jqgrid/bootstrap 등)
          </button>
        </div>
        <textarea
          className="w-full h-64 border rounded p-2 text-sm font-mono"
          value={excludes}
          onChange={e => setExcludes(e.target.value)}
          placeholder="**/assets/**&#10;**/vendor/**&#10;**/jquery/**"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={save}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
        {status && <span className={`text-sm ${status.includes("실패") ? "text-red-500" : "text-green-600"}`}>{status}</span>}
      </div>
    </div>
  );
}
