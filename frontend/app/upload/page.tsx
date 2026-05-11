"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestDocument } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ year: "2024", client: "", domain: "", project_type: "", department: "" });
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [result, setResult] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setStatus("uploading");

    const fd = new FormData();
    fd.append("file", file);
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));

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
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-lg">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold">문서 업로드</h1>
          <button onClick={() => router.push("/chat")} className="text-sm text-blue-600 hover:underline">← 채팅으로</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center">
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden" id="file-input" />
            <label htmlFor="file-input" className="cursor-pointer text-blue-600 hover:underline">
              {file ? file.name : "파일 선택"}
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
                className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder={placeholder}
                value={form[key as keyof typeof form]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                required
              />
            </div>
          ))}

          {result && (
            <p className={`text-sm ${status === "done" ? "text-green-600" : "text-red-500"}`}>{result}</p>
          )}

          <button type="submit" disabled={!file || status === "uploading"}
            className="w-full bg-blue-600 text-white rounded-xl py-2.5 font-medium hover:bg-blue-700 disabled:opacity-40 transition">
            {status === "uploading" ? "업로드 중..." : "업로드"}
          </button>
        </form>
      </div>
    </div>
  );
}
