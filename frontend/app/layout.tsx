import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "사내 제안서 RAG",
  description: "공공/SI 제안서 검색 시스템",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
