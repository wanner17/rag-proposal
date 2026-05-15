"use client";
import { Suspense, useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  agentStream,
  AgentUnavailableError,
  RetrievalScope,
  UnauthorizedError,
  type AgentWorkflowMetadata,
  type Source,
} from "@/lib/api";
import { listProjects, type Project } from "@/lib/projects";
import SourceCard from "@/components/SourceCard";
import AgentThinkingPanel, { type AgentStep } from "@/components/AgentThinkingPanel";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
  agentMetadata?: AgentWorkflowMetadata;
  agentSteps?: AgentStep[];
}

function parseContentBlocks(content: string): Array<{ type: "text" | "code"; content: string; lang?: string }> {
  const blocks: Array<{ type: "text" | "code"; content: string; lang?: string }> = [];
  const regex = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let match;
  while ((match = regex.exec(content)) !== null) {
    if (match.index > last) blocks.push({ type: "text", content: content.slice(last, match.index) });
    blocks.push({ type: "code", content: match[2], lang: match[1] || undefined });
    last = regex.lastIndex;
  }
  if (last < content.length) blocks.push({ type: "text", content: content.slice(last) });
  return blocks;
}

function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="relative my-2 rounded-lg bg-gray-900 text-sm">
      {lang && <span className="absolute top-2 left-3 text-xs text-gray-400">{lang}</span>}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 rounded px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 transition"
      >
        {copied ? "복사됨 ✓" : "복사"}
      </button>
      <pre className="overflow-x-auto px-4 pt-8 pb-4 text-gray-100 font-mono text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlugParam = searchParams.get("project");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeRunRef = useRef(0);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    void loadProjects(token);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const query = input.trim();
    const submittedProjectId = selectedProjectId || undefined;
    const submittedScope: RetrievalScope = "documents";
    const runId = activeRunRef.current + 1;
    activeRunRef.current = runId;

    setInput("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: query }]);

    const token = localStorage.getItem("token") ?? "";
    if (!token) {
      setAuthError("로그인이 만료되었습니다. 다시 로그인해 주세요.");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "로그인이 만료되었습니다. 다시 로그인해 주세요.", streaming: false },
      ]);
      setLoading(false);
      router.push("/login");
      return;
    }

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true, agentSteps: [] },
    ]);

    const history = messages
      .filter((m) => !m.streaming && m.content)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      await agentStream(
        query,
        token,
        (sources) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], sources };
            return next;
          });
        },
        (tok) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: next[next.length - 1].content + tok,
            };
            return next;
          });
        },
        (metadata) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], agentMetadata: metadata };
            return next;
          });
        },
        () => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            const msg = next[next.length - 1];
            const steps = (msg.agentSteps ?? []).map((s) =>
              s.status === "running" ? { ...s, status: "done" as const } : s
            );
            next[next.length - 1] = { ...msg, streaming: false, agentSteps: steps };
            return next;
          });
          setLoading(false);
        },
        (notice) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: next[next.length - 1].content + notice,
            };
            return next;
          });
        },
        { project_id: submittedProjectId, retrieval_scope: submittedScope, conversation_history: history },
        (name, index) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            const msg = next[next.length - 1];
            const steps = [...(msg.agentSteps ?? [])];
            steps[index] = { name, index, status: "running" };
            next[next.length - 1] = { ...msg, agentSteps: steps };
            return next;
          });
        },
        (name, index, durationMs) => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            const msg = next[next.length - 1];
            const steps = [...(msg.agentSteps ?? [])];
            steps[index] = { name, index, status: "done", durationMs };
            next[next.length - 1] = { ...msg, agentSteps: steps };
            return next;
          });
        }
      );
    } catch (err) {
      if (!isActiveRun(runId)) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized(runId, err.message);
        return;
      }
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content:
            err instanceof AgentUnavailableError
              ? err.message
              : "오류가 발생했습니다. 다시 시도해주세요.",
          streaming: false,
        };
        return next;
      });
      setLoading(false);
    }
  }

  function isActiveRun(runId: number) {
    return activeRunRef.current === runId;
  }

  async function loadProjects(token: string) {
    try {
      const items = await listProjects(token);
      const activeProjects = items.filter((project) => project.status === "active");
      setProjects(activeProjects);
      setSelectedProjectId((current) => {
        if (current) return current;
        if (projectSlugParam) {
          const matched = activeProjects.find((p) => p.slug === projectSlugParam);
          if (matched) return matched.id;
        }
        return activeProjects[0]?.id || "";
      });
    } catch {
      // silently ignore; sidebar already shows project context
    }
  }

  function handleUnauthorized(runId: number, message: string) {
    if (!isActiveRun(runId)) return;
    activeRunRef.current = runId + 1;
    localStorage.removeItem("token");
    setAuthError(message);
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = {
        role: "assistant",
        content: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
        streaming: false,
      };
      return next;
    });
    setLoading(false);
    router.push("/login");
  }

  function sourceKey(source: Source) {
    if (source.source_kind === "source_code") {
      return (
        source.point_id ??
        `${source.project_slug}:${source.relative_path}:${source.start_line}:${source.end_line}`
      );
    }
    return source.point_id ?? `${source.file}:${source.page}:${source.section}`;
  }

  function formatAgentMetadata(metadata: AgentWorkflowMetadata) {
    const runId = metadata.graph_run_id.slice(0, 8);
    const pass = metadata.selected_pass ?? "n/a";
    const retry = metadata.retry_triggered ? "retry on" : "retry off";
    const qa = metadata.answer_quality ? ` · QA ${metadata.answer_quality.status}` : "";
    return `Agent · ${metadata.framework} · pass ${pass} · ${retry}${qa} · steps ${metadata.steps.length} · run ${runId}`;
  }

  function qualityStatusLabel(status: string) {
    if (status === "passed") return "통과";
    if (status === "issues_found") return "확인 필요";
    return status;
  }

  function coverageStatusLabel(status: string) {
    if (status === "covered") return "포함";
    if (status === "missing") return "누락";
    if (status === "unavailable") return "근거 없음";
    return status;
  }

  function renderAnswerQualityReport(metadata?: AgentWorkflowMetadata) {
    const report = metadata?.answer_quality;
    if (!report) return null;

    const issueCount = report.findings.length;
    const coverageIssues = report.coverage.filter((item) => item.status !== "covered");
    const claimSupport = report.evidence_sufficiency.claim_support;
    const weakCount = claimSupport?.weak_count ?? 0;
    const statusClass =
      report.status === "passed"
        ? "bg-emerald-50 text-emerald-700"
        : "bg-amber-50 text-amber-700";

    return (
      <div className="mt-2 space-y-1 text-[11px] leading-5 text-gray-600">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full px-2 py-0.5 font-medium ${statusClass}`}>
            QA {qualityStatusLabel(report.status)}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5">
            이슈 {issueCount}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5">
            근거 약함 {weakCount}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5">
            보정 {report.revision_triggered ? report.revision_count : 0}
          </span>
        </div>
        {coverageIssues.length > 0 && (
          <div className="text-gray-500">
            Coverage:{" "}
            {coverageIssues
              .map((item) => `${item.item} ${coverageStatusLabel(item.status)}`)
              .join(", ")}
          </div>
        )}
        {report.findings.length > 0 && (
          <div className="text-gray-500">
            {report.findings.slice(0, 2).map((finding) => finding.message).join(" / ")}
          </div>
        )}
      </div>
    );
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;

  return (
    <div className="flex h-screen max-w-6xl flex-col mx-auto">
      <header className="flex items-center justify-between gap-4 border-b bg-white px-6 py-4 shadow-sm">
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-blue-700">RAG 문서 검색 시스템</h1>
          {selectedProject && (
            <p className="mt-0.5 text-xs text-gray-500">{selectedProject.name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            disabled={loading}
            className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </header>
      {authError && (
        <div className="border-b border-red-100 bg-red-50 px-6 py-2 text-sm text-red-600">
          {authError}
        </div>
      )}

      <main className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="mt-20 text-center text-gray-400">
            <p className="mb-2 text-xl">업로드 문서에 대해 질문해보세요</p>
            <p className="text-sm">예: "구축 사례 알려줘", "보안 요구사항은?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-2xl ${msg.role === "user" ? "order-2" : ""}`}>
              {msg.role === "user" ? (
                <div className="rounded-2xl px-4 py-3 whitespace-pre-wrap bg-blue-600 text-white rounded-tr-sm">
                  {msg.content}
                </div>
              ) : (
                <>
                  {msg.agentSteps && msg.agentSteps.length > 0 && (
                    <AgentThinkingPanel steps={msg.agentSteps} isStreaming={!!msg.streaming} />
                  )}
                  <div className="rounded-2xl px-4 py-3 bg-white border shadow-sm rounded-tl-sm">
                    {parseContentBlocks(msg.content).map((block, j) =>
                      block.type === "code" ? (
                        <CodeBlock key={j} code={block.content} lang={block.lang} />
                      ) : (
                        <span key={j} className="whitespace-pre-wrap">{block.content}</span>
                      )
                    )}
                    {msg.streaming && (
                      <span className="inline-block w-2 h-4 bg-gray-400 ml-1 animate-pulse rounded" />
                    )}
                  </div>
                  {msg.agentMetadata && (
                    <>
                      <div className="mt-1 text-[11px] leading-5 text-gray-500">
                        {formatAgentMetadata(msg.agentMetadata)}
                      </div>
                      {renderAnswerQualityReport(msg.agentMetadata)}
                    </>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.sources.map((src, j) => (
                        <SourceCard key={`${sourceKey(src)}-${j}`} source={src} index={j} />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      <footer className="border-t bg-white px-6 py-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            className="flex-1 rounded-xl border px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="선택한 프로젝트 문서에 대해 질문하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-40"
          >
            {loading ? "생성 중..." : "전송"}
          </button>
        </form>
      </footer>
    </div>
  );
}

export default function ChatPageWrapper() {
  return (
    <Suspense fallback={null}>
      <ChatPage />
    </Suspense>
  );
}
