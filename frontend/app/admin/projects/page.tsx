"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  CheckoutStatus,
  createProject,
  deleteProject,
  exportProject,
  getCheckoutStatus,
  importProject,
  listProjects,
  Project,
  ProjectCreatePayload,
  triggerCheckout,
  triggerIncrementalIndex,
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
  const [checkoutStatus, setCheckoutStatus] = useState<CheckoutStatus | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);

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
    const sourceConfig = form.source_config ?? EMPTY_FORM.source_config!;
    const payload = {
      ...form,
      source_config: {
        ...sourceConfig,
        repo_root: form.slug
          ? `/opt/rag-projects/${form.slug}`
          : "",
      },
    };
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
            source_config: payload.source_config,
          },
          token
        );
        setStatus(`"${updated.name}" 프로젝트를 수정했습니다.`);
      } else {
        const created = await createProject(payload, token);
        setSelectedId(created.id);
        setStatus(`"${created.name}" 프로젝트를 만들었습니다.`);
      }
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "저장에 실패했습니다.");
    }
  }

  useEffect(() => {
    if (!selectedProject?.source_config?.enabled || !token) return;
    void getCheckoutStatus(selectedProject.id, token).then(setCheckoutStatus).catch(() => {});
  }, [selectedProject, token]);

  async function handleCheckout() {
    if (!selectedProject) return;
    setSourceLoading(true);
    try {
      await triggerCheckout(selectedProject.id, token);
      const poll = setInterval(() => {
        void getCheckoutStatus(selectedProject.id, token).then((s) => {
          setCheckoutStatus(s);
          if (s.status === "done") {
            clearInterval(poll);
            void triggerIncrementalIndex(selectedProject.id, token)
              .then(() => setStatus("체크아웃 완료, 첫 인덱스를 시작했습니다."))
              .catch((e: unknown) => setStatus(e instanceof Error ? e.message : "첫 인덱스 실패"))
              .finally(() => setSourceLoading(false));
          } else if (s.status === "error") {
            clearInterval(poll);
            setStatus(`체크아웃 오류: ${s.message}`);
            setSourceLoading(false);
          }
        });
      }, 5000);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "체크아웃 실패");
      setSourceLoading(false);
    }
  }

  async function handleIncrementalIndex() {
    if (!selectedProject) return;
    setSourceLoading(true);
    try {
      await triggerIncrementalIndex(selectedProject.id, token);
      setStatus("변경분 임베딩을 시작했습니다.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "임베딩 실패");
    } finally {
      setSourceLoading(false);
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
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <p className="text-sm font-medium text-indigo-600">사내 RAG 플랫폼</p>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-slate-900">프로젝트 관리</h1>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <aside className="space-y-6 lg:col-span-1">
            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm transition-all hover:shadow-md">
              <div className="border-b border-slate-100 p-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-slate-900">프로젝트 목록</h2>
                  <button
                    onClick={startNewProject}
                    className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
                  >
                    새로 만들기
                  </button>
                </div>
              </div>
              <div className="p-4">
                <div className="max-h-96 space-y-2 overflow-y-auto">
                  {loading && <p className="px-2 py-1 text-sm text-slate-500">불러오는 중...</p>}
                  {!loading &&
                    projects.map((project) => (
                      <div
                        key={project.id}
                        className={`group flex items-center rounded-xl border text-sm transition-all ${
                          selectedId === project.id
                            ? "border-indigo-500 bg-indigo-50/50 shadow-sm ring-1 ring-indigo-500"
                            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <button
                          onClick={() => selectProject(project)}
                          className="flex-1 px-4 py-3 text-left"
                        >
                          <span className="block font-semibold text-slate-900">{project.name}</span>
                          <span className="block text-xs text-slate-500">{project.slug}</span>
                        </button>
                        <button
                          onClick={() => handleDelete(project)}
                          className="mr-2 shrink-0 rounded-lg p-2 text-slate-400 opacity-0 transition-all group-hover:opacity-100 hover:bg-red-50 hover:text-red-600"
                          title="삭제"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md">
              <h2 className="mb-3 text-lg font-bold text-slate-900">Export / Import</h2>
              <textarea
                value={bundle}
                onChange={(event) => setBundle(event.target.value)}
                className="min-h-48 w-full rounded-xl border-0 p-3 py-2 font-mono text-xs shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600"
                placeholder="내보낸 YAML/JSON 번들이 여기에 표시됩니다."
              />
              <div className="mt-3 flex gap-3">
                <button
                  onClick={handleExport}
                  className="flex-1 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50"
                >
                  내보내기
                </button>
                <button
                  onClick={handleImport}
                  className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-800"
                >
                  가져오기
                </button>
              </div>
            </section>
          </aside>

          <main className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm lg:col-span-2">
            <form onSubmit={handleSubmit} className="space-y-10">
              <div className="space-y-6">
                <div className="border-b border-slate-100 pb-5">
                  <h2 className="text-2xl font-bold leading-7 text-slate-900">
                    {selectedProject ? "프로젝트 수정" : "새 프로젝트 생성"}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    {selectedProject
                      ? "프로젝트의 상세 설정을 변경합니다."
                      : "새로운 프로젝트를 등록하고 기본 설정을 입력합니다."}
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6">
                  <div className="sm:col-span-3">
                    <Field label="Slug (ID)" value={form.slug} disabled={Boolean(selectedProject)} onChange={(slug) => setForm({ ...form, slug })} />
                  </div>
                  <div className="sm:col-span-3">
                    <Field label="이름" value={form.name} onChange={(name) => setForm({ ...form, name })} />
                  </div>
                  <div className="sm:col-span-6">
                    <label htmlFor="description" className="block text-sm font-semibold leading-6 text-slate-900">
                      설명
                    </label>
                    <div className="mt-2">
                      <textarea
                        id="description"
                        name="description"
                        rows={3}
                        value={form.description}
                        onChange={(event) => setForm({ ...form, description: event.target.value })}
                        className="block w-full rounded-xl border-0 px-4 py-2.5 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <div className="border-b border-slate-100 pb-5">
                  <h2 className="text-lg font-bold leading-7 text-slate-900">RAG 설정</h2>
                </div>
                <div className="grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6">
                  <div className="sm:col-span-2">
                    <NumberField
                      label="Top K (검색 후보 수)"
                      value={form.rag_config.top_k_default}
                      onChange={(top_k_default) =>
                        setForm({ ...form, rag_config: { ...form.rag_config, top_k_default } })
                      }
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <NumberField
                      label="Top N (LLM 전달)"
                      value={form.rag_config.top_n_default}
                      onChange={(top_n_default) =>
                        setForm({ ...form, rag_config: { ...form.rag_config, top_n_default } })
                      }
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <Field
                      label="프롬프트 프로필"
                      value={form.rag_config.prompt_profile ?? ""}
                      onChange={(prompt_profile) =>
                        setForm({ ...form, rag_config: { ...form.rag_config, prompt_profile } })
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <div className="border-b border-slate-100 pb-5">
                  <h2 className="text-lg font-bold leading-7 text-slate-900">플러그인</h2>
                </div>
                <div className="relative flex items-start">
                  <div className="flex h-6 items-center">
                    <input
                      id="proposal-plugin"
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                      checked={form.plugins[0]?.enabled ?? false}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          plugins: [{ plugin_id: "proposal", enabled: event.target.checked, config: {} }],
                        })
                      }
                    />
                  </div>
                  <div className="ml-3 text-sm leading-6">
                    <label htmlFor="proposal-plugin" className="font-bold text-slate-900">
                      제안서 플러그인 사용
                    </label>
                    <p className="text-slate-500">활성화 시 제안서 초안 생성 모드를 사용할 수 있습니다.</p>
                  </div>
                </div>
              </div>

              {(() => {
                const sc = form.source_config ?? EMPTY_FORM.source_config!;
                const setSc = (patch: Partial<typeof sc>) =>
                  setForm({ ...form, source_config: { ...sc, ...patch } });
                return (
                  <div className="space-y-6">
                    <div className="border-b border-slate-100 pb-5">
                      <h2 className="text-lg font-bold leading-7 text-slate-900">소스 저장소 설정</h2>
                    </div>
                    <div className="relative flex items-start">
                      <div className="flex h-6 items-center">
                        <input
                          id="source-enabled"
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                          checked={sc.enabled}
                          onChange={(e) => setSc({ enabled: e.target.checked })}
                        />
                      </div>
                      <div className="ml-3 text-sm leading-6">
                        <label htmlFor="source-enabled" className="font-bold text-slate-900">
                          소스코드 검색 사용
                        </label>
                        <p className="text-slate-500">SVN 저장소의 소스코드를 RAG 검색 대상으로 포함합니다.</p>
                      </div>
                    </div>

                    {sc.enabled && (
                      <>
                        <div className="grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6">
                          <div className="sm:col-span-3">
                            <Field
                              label="저장소 주소 (SVN URL)"
                              value={sc.svn_url ?? ""}
                              onChange={(v) => setSc({ svn_url: v })}
                            />
                          </div>
                          <div className="sm:col-span-3">
                            <Field
                              label="파일 저장 경로 (서버 절대경로)"
                              value={
                                form.slug
                                  ? `/opt/rag-projects/${form.slug}`
                                  : ""
                              }
                              disabled
                              onChange={() => {}}
                            />
                          </div>
                        </div>
                        {selectedProject && (
                          <div className="flex items-center gap-3 pt-2">
                            <button
                              type="button"
                              onClick={handleCheckout}
                              disabled={
                                checkoutStatus?.status === "done" ||
                                checkoutStatus?.status === "running" ||
                                sourceLoading
                              }
                              className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {checkoutStatus?.status === "running" ? "내려받는 중..." : "저장소 내려받기"}
                            </button>
                            <button
                              type="button"
                              onClick={handleIncrementalIndex}
                              disabled={sourceLoading}
                              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              변경분만 임베딩
                            </button>
                            {checkoutStatus && (
                              <span className="text-xs text-slate-500">
                                체크아웃: {checkoutStatus.status}
                                {checkoutStatus.message ? ` — ${checkoutStatus.message}` : ""}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                );
              })()}

              <div className="flex items-center justify-between gap-x-6 border-t border-slate-100 pt-6">
                <p className="text-sm text-slate-500">{status || "변경 내용을 저장하면 프로젝트 설정이 반영됩니다."}</p>
                <button
                  type="submit"
                  className="rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-bold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                >
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
    <label className="block text-sm font-semibold leading-6 text-slate-900">
      {label}
      <div className="mt-2">
        <input
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="block w-full rounded-xl border-0 px-4 py-2.5 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 transition-all focus:ring-2 focus:ring-inset focus:ring-indigo-600 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 disabled:ring-slate-200 sm:text-sm sm:leading-6"
        />
      </div>
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
    <label className="block text-sm font-semibold leading-6 text-slate-900">
      {label}
      <div className="mt-2">
        <input
          type="number"
          min={1}
          value={value}
          onChange={(event) => onChange(Number(event.target.value) || 1)}
          className="block w-full rounded-xl border-0 px-4 py-2.5 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 transition-all focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
        />
      </div>
    </label>
  );
}
