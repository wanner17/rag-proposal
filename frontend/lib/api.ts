const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";
const INCOMPLETE_RETRY_NOTICE = "※ 답변이 너무 짧아 번호 목록 형식으로 다시 생성합니다.";
const STREAM_RETRY_SEPARATOR = "\n\n---\n\n";

export class UnauthorizedError extends Error {
  constructor(message = "인증이 만료되었습니다. 다시 로그인해 주세요.") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class AgentUnavailableError extends Error {
  constructor(message = "Agent 모드를 사용할 수 없습니다. 설정 또는 백엔드 상태를 확인해 주세요.") {
    super(message);
    this.name = "AgentUnavailableError";
  }
}

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
  onDone: () => void,
  onRetry?: (notice: string) => void
) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });

  if (res.status === 401) throw new UnauthorizedError();
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
    if (data.token) handleStreamToken(data.token, onToken, onRetry);
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

export async function agentStream(
  query: string,
  token: string,
  onSource: (sources: Source[]) => void,
  onToken: (token: string) => void,
  onMetadata: (metadata: AgentWorkflowMetadata) => void,
  onDone: () => void,
  onRetry?: (notice: string) => void,
  options?: AgentQueryOptions
) {
  const res = await fetch(`${API_BASE}/agent/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, ...options }),
  });

  if (res.status === 401) throw new UnauthorizedError();
  if (res.status === 404 || res.status === 503) throw new AgentUnavailableError();
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
    if (data.token) handleStreamToken(data.token, onToken, onRetry);
    if (data.metadata) onMetadata(data.metadata);
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

function handleStreamToken(
  token: string,
  onToken: (token: string) => void,
  onRetry?: (notice: string) => void
) {
  const markerIndex = token.indexOf(INCOMPLETE_RETRY_NOTICE);
  if (markerIndex < 0) {
    onToken(token);
    return;
  }

  const prefix = token.slice(0, markerIndex);
  if (prefix) onToken(prefix);
  onRetry?.(`${STREAM_RETRY_SEPARATOR}${INCOMPLETE_RETRY_NOTICE}\n\n`);
  const remainingToken = token.slice(markerIndex + INCOMPLETE_RETRY_NOTICE.length).trimStart();
  if (remainingToken) onToken(remainingToken);
}

export async function agentQuery(query: string, token: string, options?: AgentQueryOptions) {
  const res = await fetch(`${API_BASE}/agent/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, ...options }),
  });

  if (res.status === 401) throw new UnauthorizedError();
  if (res.status === 404 || res.status === 503) throw new AgentUnavailableError();
  if (!res.ok) throw new Error("요청 실패");
  return res.json() as Promise<AgentQueryResponse>;
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

export type RetrievalScope = "documents" | "source_code";

export interface AgentQueryOptions {
  project_id?: string;
  retrieval_scope?: RetrievalScope;
}

export interface Source {
  source_kind?: "document" | "source_code";
  file?: string;
  page?: number;
  section?: string;
  score: number | null;
  project_slug?: string;
  relative_path?: string;
  language?: string;
  start_line?: number | null;
  end_line?: number | null;
  point_id?: string;
  retrieval_score?: number | null;
  rerank_score?: number | null;
  score_source?: ScoreSource;
  department?: string | null;
}

export type ScoreSource = "retrieval" | "rerank" | "unavailable" | string;

export interface AgentWorkflowStep {
  name: string;
  status: string;
  duration_ms?: number | null;
  detail: Record<string, unknown>;
}

export interface AgentAnswerQualityFinding {
  category: string;
  severity: string;
  message: string;
  detail: Record<string, unknown>;
}

export type AgentCoverageStatus = "covered" | "missing" | "unavailable" | string;

export interface AgentAnswerCoverageEntry {
  item: string;
  status: AgentCoverageStatus;
  requested_aliases: string[];
  answer_aliases: string[];
  revision_recommended: boolean;
}

export interface AgentClaimSupport {
  reviewed_count: number;
  weak_count: number;
  weak_claims: Record<string, unknown>[];
}

export interface AgentAnswerQualityReport {
  status: string;
  findings: AgentAnswerQualityFinding[];
  coverage: AgentAnswerCoverageEntry[];
  evidence_sufficiency: Record<string, unknown> & {
    claim_support?: AgentClaimSupport;
  };
  revision_recommended: boolean;
  revision_triggered: boolean;
  revision_count: number;
}

export interface AgentWorkflowMetadata {
  framework: string;
  graph_version: string;
  graph_run_id: string;
  project_id: string;
  project_slug: string;
  collection_name: string;
  selected_pass?: string | null;
  retry_triggered: boolean;
  fallback_used: boolean;
  steps: AgentWorkflowStep[];
  answer_quality?: AgentAnswerQualityReport | null;
}

export interface AgentQueryResponse {
  answer: string;
  sources: Source[];
  found: boolean;
  metadata: AgentWorkflowMetadata;
}

export {
  draftProposal,
  type ProposalDraftRequest,
  type ProposalDraftResponse,
  type ProposalSource,
  type ProposalVariant,
} from "@/plugins/proposal/api";

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
