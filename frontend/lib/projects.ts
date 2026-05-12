const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export interface ProjectPluginBinding {
  plugin_id: string;
  enabled: boolean;
  display_name_override?: string | null;
  config: Record<string, unknown>;
}

export interface ProjectRagConfig {
  collection_name: string;
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
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  slug: string;
  name: string;
  description: string;
  status: "active" | "archived";
  default_language: string;
  plugins: ProjectPluginBinding[];
  rag_config: ProjectRagConfig;
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
