const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

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

export interface ProposalDraftRequest {
  scenario_id?: string | null;
  query: string;
  department?: string | null;
  top_k?: number;
  top_n?: number;
}

export interface ProposalSource {
  file: string;
  page: number;
  section: string;
  score: number | null;
  point_id: string;
  retrieval_score?: number | null;
  rerank_score?: number | null;
  score_source: "retrieval" | "rerank" | "unavailable" | string;
  department?: string | null;
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
