const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export interface ProjectPluginBinding {
  plugin_id: string;
  enabled: boolean;
  display_name_override?: string | null;
  config: Record<string, unknown>;
}

export interface ProjectRagConfig {
  collection_name?: string | null;
  top_k_default: number;
  top_n_default: number;
  prompt_profile?: string | null;
  storage_namespace?: string | null;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
  status: "active" | "archived";
  default_language: string;
  plugins: ProjectPluginBinding[];
  rag_config: ProjectRagConfig;
  source_config: ProjectSourceConfig;
  created_at: string;
  updated_at: string;
}

export interface ProjectSourceConfig {
  enabled: boolean;
  repo_root?: string | null;
  allowed_base_path: string;
  include_globs: string[];
  exclude_globs: string[];
  max_file_size_bytes: number;
  encoding: string;
  follow_symlinks: boolean;
  svn_url?: string | null;
}

export interface ProjectCreatePayload {
  slug: string;
  name: string;
  description: string;
  status: "active" | "archived";
  default_language: string;
  plugins: ProjectPluginBinding[];
  rag_config: ProjectRagConfig;
  source_config?: ProjectSourceConfig;
}

function authHeaders(token: string, contentType = "application/json") {
  return {
    "Content-Type": contentType,
    Authorization: `Bearer ${token}`,
  };
}

export async function listProjects(token: string) {
  const res = await fetch(`${API_BASE}/projects`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("프로젝트 목록 조회 실패");
  return res.json() as Promise<Project[]>;
}

export async function createProject(payload: ProjectCreatePayload, token: string) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("프로젝트 생성 실패");
  return res.json() as Promise<Project>;
}

export async function updateProject(
  projectId: string,
  payload: Partial<Omit<ProjectCreatePayload, "slug">>,
  token: string
) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("프로젝트 수정 실패");
  return res.json() as Promise<Project>;
}

export async function deleteProject(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("프로젝트 삭제 실패");
}

export async function exportProject(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("프로젝트 내보내기 실패");
  return res.text();
}

export async function importProject(bundle: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/import`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ bundle }),
  });
  if (!res.ok) throw new Error("프로젝트 가져오기 실패");
  return res.json() as Promise<{ project: Project; imported: boolean }>;
}

export interface CheckoutStatus {
  status: "idle" | "running" | "done" | "error" | "started";
  message: string;
  progress: number;
}

export interface SourceIndexStatus {
  project_slug: string;
  collection_name: string;
  enabled: boolean;
  status: string;
  last_full_indexed_at: string | null;
  last_incremental_indexed_at: string | null;
  last_successful_revision: string | null;
  stale_lock: boolean;
  counts: Record<string, number>;
  recent_failures: { relative_path: string; reason: string }[];
}

export async function triggerCheckout(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index/checkout`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<CheckoutStatus>;
}

export async function getCheckoutStatus(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index/checkout/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("체크아웃 상태 조회 실패");
  return res.json() as Promise<CheckoutStatus>;
}

export async function getSourceIndexStatus(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("색인 상태 조회 실패");
  return res.json() as Promise<SourceIndexStatus>;
}

export async function triggerReindex(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index/reindex`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface SvnInfo {
  working_revision: string | null;
  head_revision: string | null;
}

export async function getSvnInfo(projectId: string, token: string): Promise<SvnInfo> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index/svn-info`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { working_revision: null, head_revision: null };
  return res.json() as Promise<SvnInfo>;
}

export async function triggerIncrementalIndex(projectId: string, token: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/source-index`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ changed_files: [], deleted_files: [] }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
