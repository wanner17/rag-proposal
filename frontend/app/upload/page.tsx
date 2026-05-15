"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ingestDocument } from "@/lib/api";
import { listProjects, type Project } from "@/lib/projects";

type FileStatus = "pending" | "uploading" | "done" | "error";

interface FileEntry {
  file: File;
  status: FileStatus;
  message: string;
}

function UploadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlug = searchParams.get("project");

  const [project, setProject] = useState<Project | null>(null);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    listProjects(token)
      .then((list) => {
        const found = projectSlug
          ? list.find((p) => p.slug === projectSlug)
          : list.find((p) => p.slug === "proposal-default") ?? list[0];
        if (found) setProject(found);
      })
      .catch(() => {});
  }, [router, projectSlug]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const next: FileEntry[] = Array.from(incoming).map((file) => ({
      file,
      status: "pending",
      message: "",
    }));
    setEntries((prev) => {
      const existingNames = new Set(prev.map((e) => e.file.name));
      return [...prev, ...next.filter((e) => !existingNames.has(e.file.name))];
    });
  }, []);

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };

  const removeEntry = (name: string) =>
    setEntries((prev) => prev.filter((e) => e.file.name !== name));

  async function handleUpload() {
    const pending = entries.filter((e) => e.status === "pending");
    if (!pending.length) return;
    setUploading(true);

    const token = localStorage.getItem("token") ?? "";
    const fd = new FormData();
    pending.forEach((e) => fd.append("files", e.file));
    if (project) fd.append("project_id", project.id);

    setEntries((prev) =>
      prev.map((e) => e.status === "pending" ? { ...e, status: "uploading" } : e)
    );

    try {
      const res = await ingestDocument(fd, token);
      const byName = Object.fromEntries(
        (res.files as { filename: string; chunks_indexed?: number; error?: string }[]).map(
          (f) => [f.filename, f]
        )
      );
      setEntries((prev) =>
        prev.map((e) => {
          if (e.status !== "uploading") return e;
          const r = byName[e.file.name];
          if (!r) return { ...e, status: "error", message: "응답 없음" };
          return r.error
            ? { ...e, status: "error", message: r.error }
            : { ...e, status: "done", message: `${r.chunks_indexed}개 청크` };
        })
      );
    } catch {
      setEntries((prev) =>
        prev.map((e) =>
          e.status === "uploading" ? { ...e, status: "error", message: "서버 오류" } : e
        )
      );
    } finally {
      setUploading(false);
    }
  }

  const hasPending = entries.some((e) => e.status === "pending");

  return (
    <div className="min-h-screen max-w-2xl mx-auto px-6 py-6">
      <header className="flex items-center justify-between mb-6 bg-white border shadow-sm rounded-2xl px-5 py-4">
        <div>
          <h1 className="text-xl font-bold text-blue-700">
            문서 업로드{project ? ` — ${project.name}` : ""}
          </h1>
          <p className="text-sm text-gray-500 mt-1">문서를 업로드하여 RAG 검색 인덱스에 추가합니다.</p>
        </div>
      </header>

      <section className="bg-white border rounded-2xl shadow-sm p-6 space-y-4">
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors select-none ${
            dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          <p className="text-gray-400 text-sm">
            {dragging ? "여기에 놓으세요" : "파일을 드래그하거나 클릭하여 선택 (여러 개 가능)"}
          </p>
        </div>

        {entries.length > 0 && (
          <ul className="space-y-2">
            {entries.map((e) => (
              <li key={e.file.name} className="flex items-center gap-3 text-sm">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    e.status === "done" ? "bg-green-500" :
                    e.status === "error" ? "bg-red-500" :
                    e.status === "uploading" ? "bg-yellow-400 animate-pulse" :
                    "bg-gray-300"
                  }`}
                />
                <span className="flex-1 truncate text-gray-700">{e.file.name}</span>
                {e.message && (
                  <span className={e.status === "error" ? "text-red-500" : "text-green-600"}>
                    {e.message}
                  </span>
                )}
                {e.status === "pending" && (
                  <button
                    onClick={(ev) => { ev.stopPropagation(); removeEntry(e.file.name); }}
                    className="text-gray-400 hover:text-red-500 text-xs"
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        <button
          onClick={handleUpload}
          disabled={!hasPending || uploading}
          className="w-full bg-blue-600 text-white rounded-xl py-2.5 font-medium hover:bg-blue-700 disabled:opacity-40 transition"
        >
          {uploading ? "업로드 중..." : `업로드${hasPending ? ` (${entries.filter((e) => e.status === "pending").length}개)` : ""}`}
        </button>
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
