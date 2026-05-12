import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "사내 RAG 플랫폼",
  description: "업로드 문서 기반 검색 및 질의응답 시스템",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
