"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createProject,
  deleteProject,
  exportProject,
  importProject,
  listProjects,
  Project,
  ProjectCreatePayload,
  updateProject,
} from "@/lib/projects";

const EMPTY_FORM: ProjectCreatePayload = {
  slug: "",
  name: "",
  description: "",
  status: "active",
  default_language: "ko",
  plugins: [{ plugin_id: "proposal", enabled: true, config: {} }],
  rag_config: {
    top_k_default: 20,
    top_n_default: 5,
    prompt_profile: "",
  },
  source_config: {
    enabled: false,
    svn_url: "",
    repo_root: "",
    allowed_base_path: "/opt/rag-projects",
    include_globs: [],
    exclude_globs: [],
    max_file_size_bytes: 1048576,
    encoding: "utf-8",
    follow_symlinks: false,
  },
};

export default function ProjectAdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [form, setForm] = useState<ProjectCreatePayload>(EMPTY_FORM);
  const [bundle, setBundle] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedId) ?? null,
    [projects, selectedId]
  );

  useEffect(() => {
    const authToken = localStorage.getItem("token");
    if (!authToken) {
      router.push("/login");
      return;
    }
    setToken(authToken);
    void refresh(authToken);
  }, [router]);

  async function refresh(authToken = token) {
    setLoading(true);
    try {
      const items = await listProjects(authToken);
      setProjects(items);
      const nextSelected = selectedId || items[0]?.id || "";
      setSelectedId(nextSelected);
      const project = items.find((item) => item.id === nextSelected);
      if (project) setForm(toForm(project));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "프로젝트를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function selectProject(project: Project) {
    setSelectedId(project.id);
    setForm(toForm(project));
    setStatus("");
  }

  function startNewProject() {
    setSelectedId("");
    setForm(EMPTY_FORM);
    setStatus("");
  }

  async function handleDelete(project: Project) {
    if (!window.confirm(`"${project.name}" 프로젝트를 삭제할까요?\n되돌릴 수 없습니다.`)) return;
    try {
      await deleteProject(project.id, token);
      setSelectedId("");
      setForm(EMPTY_FORM);
      setStatus(`"${project.name}" 프로젝트를 삭제했습니다.`);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "삭제에 실패했습니다.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      if (selectedProject) {
        const updated = await updateProject(
          selectedProject.id,
          {
            name: form.name,
            description: form.description,
            status: form.status,
            default_language: form.default_language,
            plugins: form.plugins,
            rag_config: form.rag_config,
            source_config: form.source_config,
          },
          token
        );
        setStatus(`"${updated.name}" 프로젝트를 수정했습니다.`);
      } else {
        const created = await createProject(form, token);
        setSelectedId(created.id);
        setStatus(`"${created.name}" 프로젝트를 만들었습니다.`);
      }
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "저장에 실패했습니다.");
    }
  }

  async function handleExport() {
    if (!selectedProject) return;
    try {
      const text = await exportProject(selectedProject.id, token);
      setBundle(text);
      setStatus("프로젝트 번들을 아래 편집기에 불러왔습니다.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "내보내기에 실패했습니다.");
    }
  }

  async function handleImport() {
    if (!bundle.trim()) return;
    try {
      const result = await importProject(bundle, token);
      setSelectedId(result.project.id);
      setStatus(`"${result.project.name}" 프로젝트를 가져왔습니다.`);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "가져오기에 실패했습니다.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b pb-4">
          <div>
            <p className="text-sm text-slate-500">사내 RAG 플랫폼</p>
            <h1 className="text-2xl font-bold text-slate-900">프로젝트 관리</h1>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <aside className="space-y-4">
            <section className="rounded-lg border bg-white p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">프로젝트</h2>
                <button onClick={startNewProject} className="rounded-md border px-3 py-1.5 text-sm">
                  새로 만들기
                </button>
              </div>
              <div className="space-y-2">
                {loading && <p className="text-sm text-slate-500">불러오는 중...</p>}
                {!loading &&
                  projects.map((project) => (
                    <div
                      key={project.id}
                      className={`flex items-center rounded-md border text-sm ${
                        selectedId === project.id ? "border-blue-500 bg-blue-50" : "bg-white"
                      }`}
                    >
                      <button
                        onClick={() => selectProject(project)}
                        className="flex-1 px-3 py-3 text-left"
                      >
                        <span className="block font-medium">{project.name}</span>
                        <span className="block text-xs text-slate-500">{project.slug}</span>
                      </button>
                      <button
                        onClick={() => handleDelete(project)}
                        className="shrink-0 px-2 py-1 mr-2 text-xs text-red-500 hover:bg-red-50 rounded"
                        title="삭제"
                      >
                        삭제
                      </button>
                    </div>
                  ))}
              </div>
            </section>

            <section className="rounded-lg border bg-white p-4">
              <h2 className="mb-3 font-semibold">Export / Import</h2>
              <textarea
                value={bundle}
                onChange={(event) => setBundle(event.target.value)}
                className="min-h-48 w-full rounded-md border px-3 py-2 font-mono text-xs"
                placeholder="내보낸 YAML/JSON 번들이 여기에 표시됩니다."
              />
              <div className="mt-3 flex gap-2">
                <button onClick={handleExport} className="rounded-md border px-3 py-2 text-sm">
                  내보내기
                </button>
                <button onClick={handleImport} className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white">
                  가져오기
                </button>
              </div>
            </section>
          </aside>

          <main className="rounded-lg border bg-white p-5">
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Slug" value={form.slug} disabled={Boolean(selectedProject)} onChange={(slug) => setForm({ ...form, slug })} />
                <Field label="이름" value={form.name} onChange={(name) => setForm({ ...form, name })} />
                <Field label="기본 언어" value={form.default_language} onChange={(default_language) => setForm({ ...form, default_language })} />
              </div>

              <label className="block text-sm font-medium">
                <span className="mb-1 block">설명</span>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  className="min-h-24 w-full rounded-md border px-3 py-2 text-sm"
                />
              </label>

              <div className="grid gap-4 md:grid-cols-3">
                <NumberField
                  label="Top K"
                  value={form.rag_config.top_k_default}
                  onChange={(top_k_default) =>
                    setForm({ ...form, rag_config: { ...form.rag_config, top_k_default } })
                  }
                />
                <NumberField
                  label="Top N"
                  value={form.rag_config.top_n_default}
                  onChange={(top_n_default) =>
                    setForm({ ...form, rag_config: { ...form.rag_config, top_n_default } })
                  }
                />
                <Field
                  label="프롬프트 프로필"
                  value={form.rag_config.prompt_profile ?? ""}
                  onChange={(prompt_profile) =>
                    setForm({ ...form, rag_config: { ...form.rag_config, prompt_profile } })
                  }
                />
              </div>

              <label className="flex items-center gap-3 rounded-md border px-3 py-3 text-sm">
                <input
                  type="checkbox"
                  checked={form.plugins[0]?.enabled ?? false}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      plugins: [{ plugin_id: "proposal", enabled: event.target.checked, config: {} }],
                    })
                  }
                />
                제안서 플러그인 사용
              </label>

              {/* 소스 저장소 설정 */}
              {(() => {
                const sc = form.source_config ?? EMPTY_FORM.source_config!;
                const setSc = (patch: Partial<typeof sc>) =>
                  setForm({ ...form, source_config: { ...sc, ...patch } });
                return (
                  <fieldset className="rounded-lg border p-4 space-y-4">
                    <legend className="px-1 text-sm font-semibold text-slate-700">소스 저장소 설정</legend>

                    <label className="flex items-center gap-3 text-sm">
                      <input
                        type="checkbox"
                        checked={sc.enabled}
                        onChange={(e) => setSc({ enabled: e.target.checked })}
                      />
                      소스코드 검색 사용
                    </label>

                    {sc.enabled && (
                      <>
                        <div className="grid gap-3 md:grid-cols-2">
                          <Field
                            label="저장소 주소 (SVN URL)"
                            value={sc.svn_url ?? ""}
                            onChange={(v) => setSc({ svn_url: v })}
                          />
                          <Field
                            label="파일 저장 경로 (서버 절대경로)"
                            value={sc.repo_root ?? ""}
                            onChange={(v) => setSc({ repo_root: v })}
                          />
                        </div>
                      </>
                    )}
                  </fieldset>
                );
              })()}

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-slate-600">{status || "변경 내용을 저장하면 프로젝트 설정이 반영됩니다."}</p>
                <button type="submit" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white">
                  {selectedProject ? "수정 저장" : "프로젝트 생성"}
                </button>
              </div>
            </form>
          </main>
        </div>
      </div>
    </div>
  );
}

function toForm(project: Project): ProjectCreatePayload {
  const sc = project.source_config;
  return {
    slug: project.slug,
    name: project.name,
    description: project.description,
    status: project.status,
    default_language: project.default_language,
    plugins: project.plugins.length ? project.plugins : [{ plugin_id: "proposal", enabled: false, config: {} }],
    rag_config: project.rag_config,
    source_config: sc
      ? {
          ...sc,
          svn_url: sc.svn_url ?? "",
          repo_root: sc.repo_root ?? "",
        }
      : EMPTY_FORM.source_config,
  };
}

function Field({
  label,
  value,
  disabled = false,
  onChange,
}: {
  label: string;
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm font-medium">
      <span className="mb-1 block">{label}</span>
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm disabled:bg-slate-100"
      />
    </label>
  );
}


function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-sm font-medium">
      <span className="mb-1 block">{label}</span>
      <input
        type="number"
        min={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value) || 1)}
        className="w-full rounded-md border px-3 py-2 text-sm"
      />
    </label>
  );
}
