"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ingestDocument } from "@/lib/api";
import { listProjects, type Project } from "@/lib/projects";

function UploadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlug = searchParams.get("project");

  const [project, setProject] = useState<Project | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ year: "2024", client: "", domain: "", project_type: "", department: "" });
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [result, setResult] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    listProjects(token)
      .then((list) => {
        const found = projectSlug ? list.find((p) => p.slug === projectSlug) : list[0];
        if (found) setProject(found);
      })
      .catch(() => {});
  }, [router, projectSlug]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setStatus("uploading");
    setResult("");

    const fd = new FormData();
    fd.append("file", file);
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    if (project) fd.append("project_id", project.id);

    try {
      const token = localStorage.getItem("token") ?? "";
      const res = await ingestDocument(fd, token);
      setResult(`완료: ${res.chunks_indexed}개 청크 인덱싱`);
      setStatus("done");
    } catch {
      setResult("업로드 실패. 파일 형식 또는 서버 상태를 확인하세요.");
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen max-w-2xl mx-auto px-6 py-6">
      <header className="flex items-center justify-between mb-6 bg-white border shadow-sm rounded-2xl px-5 py-4">
        <div>
          <h1 className="text-xl font-bold text-blue-700">
            문서 업로드{project ? ` — ${project.name}` : ""}
          </h1>
          <p className="text-sm text-gray-500 mt-1">PDF, HWP 문서를 업로드하여 RAG 검색 인덱스에 추가합니다.</p>
        </div>
      </header>

      <section className="bg-white border rounded-2xl shadow-sm p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-blue-400 transition-colors">
            <input
              type="file"
              accept=".pdf,.hwp,.hwpx,.docx"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setStatus("idle"); setResult(""); }}
              className="hidden"
              id="file-input"
            />
            <label htmlFor="file-input" className="cursor-pointer">
              {file ? (
                <span className="text-blue-700 font-medium">{file.name}</span>
              ) : (
                <span className="text-gray-400">파일 선택 (PDF, HWP, DOCX)</span>
              )}
            </label>
          </div>

          {[
            { key: "year", label: "연도", placeholder: "2024" },
            { key: "client", label: "발주처", placeholder: "교육청" },
            { key: "domain", label: "도메인", placeholder: "이러닝" },
            { key: "project_type", label: "사업유형", placeholder: "플랫폼 구축" },
            { key: "department", label: "담당부서", placeholder: "공공사업팀" },
          ].map(({ key, label, placeholder }) => (
            <div key={key} className="flex items-center gap-3">
              <label className="w-20 text-sm text-gray-600 shrink-0">{label}</label>
              <input
                className="flex-1 border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder={placeholder}
                value={form[key as keyof typeof form]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                required
              />
            </div>
          ))}

          {result && (
            <p className={`text-sm rounded-lg px-3 py-2 ${status === "done" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
              {result}
            </p>
          )}

          <button
            type="submit"
            disabled={!file || status === "uploading"}
            className="w-full bg-blue-600 text-white rounded-xl py-2.5 font-medium hover:bg-blue-700 disabled:opacity-40 transition"
          >
            {status === "uploading" ? "업로드 중..." : "업로드"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default function UploadPageWrapper() {
  return (
    <Suspense fallback={null}>
      <UploadPage />
    </Suspense>
  );
}
