"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  agentStream,
  AgentUnavailableError,
  chatStream,
  UnauthorizedError,
  type AgentWorkflowMetadata,
  type Source,
} from "@/lib/api";
import SourceCard from "@/components/SourceCard";
import AppNav from "@/components/AppNav";

type ChatMode = "stream" | "agent" | "compare";
type ComparisonSideKey = "stream" | "agent";

interface ComparisonSide {
  content: string;
  sources: Source[];
  loading: boolean;
  error: string;
  agentMetadata?: AgentWorkflowMetadata;
}

interface ComparisonRun {
  runId: number;
  query: string;
  stream: ComparisonSide;
  agent: ComparisonSide;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
  mode?: ChatMode;
  agentMetadata?: AgentWorkflowMetadata;
  comparison?: ComparisonRun;
}

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [chatMode, setChatMode] = useState<ChatMode>("stream");
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeRunRef = useRef(0);
  const comparisonFinishedRef = useRef(new Map<number, Set<ComparisonSideKey>>());

  useEffect(() => {
    if (!localStorage.getItem("token")) router.push("/login");
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const query = input.trim();
    const submittedMode = chatMode;
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
        {
          role: "assistant",
          content: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
          streaming: false,
          mode: submittedMode,
        },
      ]);
      setLoading(false);
      router.push("/login");
      return;
    }

    if (submittedMode === "compare") {
      comparisonFinishedRef.current.set(runId, new Set());
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "",
          mode: "compare",
          comparison: createComparisonRun(runId, query),
        },
      ]);
      void runComparison(query, token, runId);
      return;
    }

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true, mode: submittedMode },
    ]);

    try {
      if (submittedMode === "agent") {
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
              next[next.length - 1] = { ...next[next.length - 1], streaming: false };
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
          }
        );
        return;
      }

      await chatStream(
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
        () => {
          if (!isActiveRun(runId)) return;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], streaming: false };
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
        }
      );
    } catch (err) {
      if (!isActiveRun(runId)) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized(runId, err.message, submittedMode);
        return;
      }

      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          mode: submittedMode,
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

  function createComparisonRun(runId: number, query: string): ComparisonRun {
    return {
      runId,
      query,
      stream: createComparisonSide(),
      agent: createComparisonSide(),
    };
  }

  function createComparisonSide(): ComparisonSide {
    return {
      content: "",
      sources: [],
      loading: true,
      error: "",
    };
  }

  function handleUnauthorized(runId: number, message: string, mode: ChatMode) {
    if (!isActiveRun(runId)) return;
    activeRunRef.current = runId + 1;
    localStorage.removeItem("token");
    setAuthError(message);
    setMessages((prev) => {
      if (mode !== "compare") {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
          streaming: false,
          mode,
        };
        return next;
      }

      return prev.map((msg) => {
        if (msg.comparison?.runId !== runId) return msg;
        return {
          ...msg,
          comparison: {
            ...msg.comparison,
            stream: {
              ...msg.comparison.stream,
              loading: false,
              error: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
            },
            agent: {
              ...msg.comparison.agent,
              loading: false,
              error: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
            },
          },
        };
      });
    });
    setLoading(false);
    router.push("/login");
  }

  async function runComparison(query: string, token: string, runId: number) {
    await runComparisonStream(query, token, runId);
    if (!isActiveRun(runId)) return;
    await runComparisonAgent(query, token, runId);
  }

  async function runComparisonStream(query: string, token: string, runId: number) {
    try {
      await chatStream(
        query,
        token,
        (sources) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "stream", { sources });
        },
        (tok) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "stream", (side) => ({
            content: side.content + tok,
          }));
        },
        () => {
          if (!isActiveRun(runId)) return;
          finishComparisonSide(runId, "stream", { loading: false });
        },
        (notice) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "stream", (side) => ({
            content: `${side.content}${notice}`,
          }));
        }
      );
    } catch (err) {
      if (!isActiveRun(runId)) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized(runId, err.message, "compare");
        return;
      }

      finishComparisonSide(runId, "stream", {
        loading: false,
        error: "오류가 발생했습니다. 다시 시도해주세요.",
      });
    }
  }

  async function runComparisonAgent(query: string, token: string, runId: number) {
    try {
      await agentStream(
        query,
        token,
        (sources) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "agent", { sources });
        },
        (tok) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "agent", (side) => ({
            content: side.content + tok,
          }));
        },
        (metadata) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "agent", { agentMetadata: metadata });
        },
        () => {
          if (!isActiveRun(runId)) return;
          finishComparisonSide(runId, "agent", { loading: false });
        },
        (notice) => {
          if (!isActiveRun(runId)) return;
          updateComparisonSide(runId, "agent", (side) => ({
            content: `${side.content}${notice}`,
          }));
        }
      );
    } catch (err) {
      if (!isActiveRun(runId)) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized(runId, err.message, "compare");
        return;
      }

      finishComparisonSide(runId, "agent", {
        loading: false,
        error:
          err instanceof AgentUnavailableError
            ? err.message
            : "오류가 발생했습니다. 다시 시도해주세요.",
      });
    }
  }

  function updateComparisonSide(
    runId: number,
    sideKey: ComparisonSideKey,
    patch: Partial<ComparisonSide> | ((side: ComparisonSide) => Partial<ComparisonSide>)
  ) {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.comparison?.runId !== runId) return msg;
        const currentSide = msg.comparison[sideKey];
        const nextPatch = typeof patch === "function" ? patch(currentSide) : patch;
        return {
          ...msg,
          comparison: {
            ...msg.comparison,
            [sideKey]: {
              ...currentSide,
              ...nextPatch,
            },
          },
        };
      })
    );
  }

  function finishComparisonSide(
    runId: number,
    sideKey: ComparisonSideKey,
    patch: Partial<ComparisonSide>
  ) {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.comparison?.runId !== runId) return msg;
        const currentSide = msg.comparison[sideKey];
        const updatedComparison = {
          ...msg.comparison,
          [sideKey]: {
            ...currentSide,
            ...patch,
          },
        };
        return {
          ...msg,
          comparison: updatedComparison,
        };
      })
    );

    const finishedSides = comparisonFinishedRef.current.get(runId) ?? new Set<ComparisonSideKey>();
    finishedSides.add(sideKey);
    comparisonFinishedRef.current.set(runId, finishedSides);
    if (finishedSides.size === 2 && isActiveRun(runId)) {
      setLoading(false);
      comparisonFinishedRef.current.delete(runId);
    }
  }

  function sourceKey(source: Source) {
    return source.point_id ?? `${source.file}:${source.page}:${source.section}`;
  }

  function sourceLabel(source: Source) {
    const section = source.section ? ` · ${source.section}` : "";
    return `${source.file} p.${source.page}${section}`;
  }

  function getSourceOverlap(streamSources: Source[], agentSources: Source[]) {
    const agentByKey = new Map(agentSources.map((source) => [sourceKey(source), source]));
    return streamSources
      .filter((source) => agentByKey.has(sourceKey(source)))
      .map((source) => sourceLabel(source));
  }

  function formatAgentMetadata(metadata: AgentWorkflowMetadata) {
    const runId = metadata.graph_run_id.slice(0, 8);
    const pass = metadata.selected_pass ?? "n/a";
    const retry = metadata.retry_triggered ? "retry on" : "retry off";
    return `Agent · ${metadata.framework} · pass ${pass} · ${retry} · steps ${metadata.steps.length} · run ${runId}`;
  }

  function renderComparisonSide(
    title: string,
    side: ComparisonSide,
    sideKey: ComparisonSideKey
  ) {
    const status = side.loading ? "생성 중" : side.error ? "오류" : "완료";
    return (
      <section className="min-w-0 rounded-xl border bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
              side.error
                ? "bg-red-50 text-red-600"
                : side.loading
                  ? "bg-blue-50 text-blue-700"
                  : "bg-emerald-50 text-emerald-700"
            }`}
          >
            {status}
          </span>
        </div>
        <div className="min-h-24 whitespace-pre-wrap rounded-lg bg-gray-50 px-3 py-2 text-sm leading-6 text-gray-800">
          {side.error ||
            side.content ||
            (side.loading ? "답변을 생성하고 있습니다..." : "응답이 없습니다.")}
          {side.loading && !side.error && (
            <span className="ml-1 inline-block h-4 w-2 animate-pulse rounded bg-gray-400 align-middle" />
          )}
        </div>
        {sideKey === "agent" && side.agentMetadata && (
          <div className="mt-2 text-[11px] leading-5 text-gray-500">
            {formatAgentMetadata(side.agentMetadata)}
          </div>
        )}
        <div className="mt-3 text-xs font-medium text-gray-600">
          출처 {side.sources.length}개
        </div>
        {side.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            {side.sources.map((src, j) => (
              <SourceCard key={`${sourceKey(src)}-${j}`} source={src} index={j} />
            ))}
          </div>
        )}
      </section>
    );
  }

  function renderComparison(comparison: ComparisonRun) {
    const overlap = getSourceOverlap(comparison.stream.sources, comparison.agent.sources);
    const visibleOverlap = overlap.slice(0, 3);
    const remainingOverlap = overlap.length - visibleOverlap.length;

    return (
      <div className="w-full max-w-5xl">
        <div className="mb-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Compare
              </div>
              <div className="text-sm font-medium text-gray-800">{comparison.query}</div>
            </div>
            <div className="text-xs text-gray-600">
              Basic {comparison.stream.sources.length} · Agent {comparison.agent.sources.length} · 겹친 출처 {overlap.length}
            </div>
          </div>
          {visibleOverlap.length > 0 && (
            <div className="mt-2 text-xs leading-5 text-gray-500">
              공통: {visibleOverlap.join(", ")}
              {remainingOverlap > 0 ? ` 외 ${remainingOverlap}개` : ""}
            </div>
          )}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {renderComparisonSide("Basic · /api/chat/stream", comparison.stream, "stream")}
          {renderComparisonSide("Agent · /api/agent/stream", comparison.agent, "agent")}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen max-w-6xl flex-col mx-auto">
      <header className="flex items-center justify-between gap-4 border-b bg-white px-6 py-4 shadow-sm">
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-blue-700">RAG 문서 검색 시스템</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg border border-gray-200 bg-gray-50 p-1 text-xs font-medium">
            <button
              type="button"
              disabled={loading}
              onClick={() => setChatMode("stream")}
              className={`rounded-md px-3 py-1.5 transition ${
                chatMode === "stream"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              } disabled:opacity-50`}
            >
              기본
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setChatMode("agent")}
              className={`rounded-md px-3 py-1.5 transition ${
                chatMode === "agent"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              } disabled:opacity-50`}
            >
              Agent
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setChatMode("compare")}
              className={`rounded-md px-3 py-1.5 transition ${
                chatMode === "compare"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              } disabled:opacity-50`}
            >
              Compare
            </button>
          </div>
          <AppNav />
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
            <div className={`${msg.comparison ? "w-full" : "max-w-2xl"} ${msg.role === "user" ? "order-2" : ""}`}>
              {msg.comparison ? (
                renderComparison(msg.comparison)
              ) : (
                <>
                  <div
                    className={`rounded-2xl px-4 py-3 whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-tr-sm"
                        : "bg-white border shadow-sm rounded-tl-sm"
                    }`}
                  >
                    {msg.content}
                    {msg.streaming && (
                      <span className="inline-block w-2 h-4 bg-gray-400 ml-1 animate-pulse rounded" />
                    )}
                  </div>
                  {msg.agentMetadata && (
                    <div className="mt-1 text-[11px] leading-5 text-gray-500">
                      {formatAgentMetadata(msg.agentMetadata)}
                    </div>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.sources.map((src, j) => (
                        <SourceCard key={j} source={src} index={j} />
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
            placeholder="업로드 문서에 대해 질문하세요..."
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
