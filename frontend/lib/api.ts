const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("로그인 실패");
  return res.json() as Promise<{ access_token: string }>;
}

export async function chatStream(
  query: string,
  token: string,
  onSource: (sources: Source[]) => void,
  onToken: (token: string) => void,
  onDone: () => void
) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) throw new Error("요청 실패");
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const processEvent = (event: string) => {
    const line = event.split("\n").find((item) => item.startsWith("data:"));
    if (!line) return false;
    const payload = line.slice(5).trim();
    if (payload === "[DONE]") {
      onDone();
      return true;
    }
    const data = JSON.parse(payload);
    if (data.sources) onSource(data.sources);
    if (data.token) onToken(data.token);
    return false;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      if (processEvent(event)) return;
    }
  }
  if (buffer.trim() && processEvent(buffer)) return;
  onDone();
}

export async function ingestDocument(formData: FormData, token: string) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) throw new Error("업로드 실패");
  return res.json();
}

export async function draftProposal(request: ProposalDraftRequest, token: string) {
  const res = await fetch(`${API_BASE}/proposals/draft`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const message = await res.text().catch(() => "");
    throw new Error(message || "제안서 초안 생성 실패");
  }

  return res.json() as Promise<ProposalDraftResponse>;
}

export async function listDocuments(token: string) {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("문서 목록 조회 실패");
  return res.json() as Promise<DocumentSearchResponse>;
}

export async function searchDocuments(request: DocumentSearchRequest, token: string) {
  const res = await fetch(`${API_BASE}/documents/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error("문서 검색 실패");
  return res.json() as Promise<DocumentSearchResponse>;
}

export async function deleteDocument(file: string, token: string) {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(file)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("문서 삭제 실패");
  return res.json() as Promise<DocumentDeleteResponse>;
}

export interface Source {
  file: string;
  page: number;
  section: string;
  score: number | null;
  point_id?: string;
  retrieval_score?: number | null;
  rerank_score?: number | null;
  score_source?: ScoreSource;
  department?: string | null;
}

export type ScoreSource = "retrieval" | "rerank" | "unavailable" | string;

export interface ProposalDraftRequest {
  scenario_id?: string | null;
  query: string;
  department?: string | null;
  top_k?: number;
  top_n?: number;
}

export interface ProposalSource extends Source {
  point_id: string;
  score_source: ScoreSource;
}

export interface ProposalVariant {
  variant_id: string;
  title: string;
  strategy: string;
  draft_markdown: string;
  sources: ProposalSource[];
  warnings: string[];
  quality_summary?: string | null;
}

export interface ProposalDraftResponse {
  request_id: string;
  found: boolean;
  status: "ok" | "no_results" | "partial" | "error" | string;
  scenario_id?: string | null;
  department_scope?: string | null;
  variants: ProposalVariant[];
  shared_sources: ProposalSource[];
  warnings: string[];
  no_results_message?: string | null;
}

export interface DocumentSummary {
  file: string;
  department?: string | null;
  year?: number | null;
  client?: string | null;
  domain?: string | null;
  project_type?: string | null;
  pages: number[];
  sections: string[];
  chunk_count: number;
}

export interface DocumentSearchRequest {
  query: string;
  top_k?: number;
}

export interface DocumentSearchHit {
  point_id: string;
  file: string;
  page: number;
  section: string;
  department?: string | null;
  score?: number | null;
  score_source: ScoreSource;
  text: string;
}

export interface DocumentSearchResponse {
  found: boolean;
  documents: DocumentSummary[];
  hits: DocumentSearchHit[];
}

export interface DocumentDeleteResponse {
  deleted: boolean;
  file: string;
  indexed_chunks_deleted: boolean;
  source_file_deleted: boolean;
  message: string;
}
