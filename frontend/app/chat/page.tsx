"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { chatStream, Source } from "@/lib/api";
import SourceCard from "@/components/SourceCard";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
}

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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
    setInput("");
    setLoading(true);

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    // 스트리밍 답변 자리 미리 추가
    setMessages((prev) => [...prev, { role: "assistant", content: "", streaming: true }]);

    const token = localStorage.getItem("token") ?? "";
    try {
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
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "오류가 발생했습니다. 다시 시도해주세요.",
          streaming: false,
        };
        return next;
      });
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("token");
    router.push("/login");
  }

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b shadow-sm">
        <h1 className="text-lg font-bold text-blue-700">제안서 RAG 시스템</h1>
        <div className="flex gap-3">
          <a href="/proposals" className="text-sm text-gray-500 hover:text-gray-700">제안서 초안</a>
          <a href="/upload" className="text-sm text-gray-500 hover:text-gray-700">문서 업로드</a>
          <button onClick={handleLogout} className="text-sm text-red-500 hover:text-red-700">로그아웃</button>
        </div>
      </header>

      {/* 메시지 목록 */}
      <main className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-xl mb-2">제안서에 대해 질문해보세요</p>
            <p className="text-sm">예: "LMS 구축 사례 알려줘", "보안 요구사항은?"</p>
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
            placeholder="제안서에 대해 질문하세요..."
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
