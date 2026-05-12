"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  agentQuery,
  AgentUnavailableError,
  chatStream,
  UnauthorizedError,
  type AgentWorkflowMetadata,
  type Source,
} from "@/lib/api";
import SourceCard from "@/components/SourceCard";
import AppNav from "@/components/AppNav";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
  mode?: "stream" | "agent";
  agentMetadata?: AgentWorkflowMetadata;
}

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [agentMode, setAgentMode] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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
    const submittedMode = agentMode ? "agent" : "stream";
    setInput("");
    setLoading(true);

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    // 스트리밍 답변 자리 미리 추가
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true, mode: submittedMode },
    ]);

    const token = localStorage.getItem("token") ?? "";
    if (!token) {
      setAuthError("로그인이 만료되었습니다. 다시 로그인해 주세요.");
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
      return;
    }

    try {
      if (submittedMode === "agent") {
        const response = await agentQuery(query, token);
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            ...next[next.length - 1],
            content: response.answer,
            sources: response.sources,
            streaming: false,
            agentMetadata: response.metadata,
          };
          return next;
        });
        setLoading(false);
        return;
      }

      await chatStream(
        query,
        token,
        (sources) => {
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], sources };
            return next;
          });
        },
        (tok) => {
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
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], streaming: false };
            return next;
          });
          setLoading(false);
        }
      );
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        localStorage.removeItem("token");
        setAuthError(err.message);
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
            streaming: false,
            mode: submittedMode,
          };
          return next;
        });
        setLoading(false);
        router.push("/login");
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

  function formatAgentMetadata(metadata: AgentWorkflowMetadata) {
    const runId = metadata.graph_run_id.slice(0, 8);
    const pass = metadata.selected_pass ?? "n/a";
    const retry = metadata.retry_triggered ? "retry on" : "retry off";
    return `Agent · ${metadata.framework} · pass ${pass} · ${retry} · steps ${metadata.steps.length} · run ${runId}`;
  }

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      {/* 헤더 */}
      <header className="flex items-center justify-between gap-4 px-6 py-4 bg-white border-b shadow-sm">
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-blue-700">RAG 문서 검색 시스템</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg border border-gray-200 bg-gray-50 p-1 text-xs font-medium">
            <button
              type="button"
              disabled={loading}
              onClick={() => setAgentMode(false)}
              className={`rounded-md px-3 py-1.5 transition ${
                !agentMode ? "bg-white text-blue-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
              } disabled:opacity-50`}
            >
              기본
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setAgentMode(true)}
              className={`rounded-md px-3 py-1.5 transition ${
                agentMode ? "bg-white text-blue-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
              } disabled:opacity-50`}
            >
              Agent
            </button>
          </div>
          <AppNav />
        </div>
      </header>
      {authError && (
        <div className="px-6 py-2 text-sm text-red-600 bg-red-50 border-b border-red-100">
          {authError}
        </div>
      )}

      {/* 메시지 목록 */}
      <main className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-xl mb-2">업로드 문서에 대해 질문해보세요</p>
            <p className="text-sm">예: "구축 사례 알려줘", "보안 요구사항은?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-2xl ${msg.role === "user" ? "order-2" : ""}`}>
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
              {/* 출처 카드 */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.sources.map((src, j) => (
                    <SourceCard key={j} source={src} index={j} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      {/* 입력창 */}
      <footer className="px-6 py-4 bg-white border-t">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            className="flex-1 border rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            placeholder="업로드 문서에 대해 질문하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-blue-600 text-white px-5 py-2.5 rounded-xl hover:bg-blue-700 disabled:opacity-40 transition text-sm font-medium"
          >
            {loading ? "생성 중..." : "전송"}
          </button>
        </form>
      </footer>
    </div>
  );
}
