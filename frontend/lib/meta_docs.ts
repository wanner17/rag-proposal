const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export type MetaDocType =
  | "project_summary"
  | "menu_map"
  | "feature_map"
  | "db_schema_summary"
  | "architecture";

export const META_DOC_LABELS: Record<MetaDocType, string> = {
  project_summary: "프로젝트 요약",
  menu_map: "메뉴 구조",
  feature_map: "기능 맵",
  db_schema_summary: "DB 스키마 요약",
  architecture: "아키텍처",
};

export const META_DOC_TYPES: MetaDocType[] = [
  "project_summary",
  "menu_map",
  "feature_map",
  "db_schema_summary",
  "architecture",
];

export interface MetaDocResponse {
  doc_type: MetaDocType;
  content: string | null;
  exists: boolean;
}

export interface AllMetaDocsResponse {
  project_summary: MetaDocResponse;
  menu_map: MetaDocResponse;
  feature_map: MetaDocResponse;
  db_schema_summary: MetaDocResponse;
  architecture: MetaDocResponse;
}

function authHeaders(token: string): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export async function getAllMetaDocs(
  projectId: string,
  token: string
): Promise<AllMetaDocsResponse> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/meta-docs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("메타 문서 조회 실패");
  return res.json();
}

export async function saveMetaDoc(
  projectId: string,
  docType: MetaDocType,
  content: string,
  token: string
): Promise<MetaDocResponse> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/meta-docs/${docType}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("메타 문서 저장 실패");
  return res.json();
}

export async function generateMetaDocDraft(
  projectId: string,
  docType: MetaDocType,
  token: string
): Promise<{ draft: string }> {
  const res = await fetch(
    `${API_BASE}/projects/${projectId}/meta-docs/${docType}/generate`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` } }
  );
  if (!res.ok) throw new Error("자동 초안 생성 실패");
  return res.json();
}
