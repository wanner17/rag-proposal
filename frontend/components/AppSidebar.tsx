"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { listProjects, type Project } from "@/lib/projects";

export default function AppSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null);

  // 현재 활성 프로젝트: URL의 ?project= 파라미터 또는 /projects/[slug] 경로에서 추출
  const projectParam = searchParams.get("project");
  const slugFromPath = pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
  const currentSlug = slugFromPath ?? projectParam ?? null;

  useEffect(() => {
    if (currentSlug) setExpandedSlug(currentSlug);
  }, [currentSlug]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    listProjects(token)
      .then((list) => setProjects(list.filter((p) => p.status === "active")))
      .catch(() => {});
  }, []);

  function handleLogout() {
    localStorage.removeItem("token");
    router.push("/login");
  }

  function hasPlugin(project: Project, pluginId: string) {
    return project.plugins?.some((p) => p.plugin_id === pluginId && p.enabled);
  }

  function isItemActive(basePath: string, slug: string) {
    return pathname === basePath && searchParams.get("project") === slug;
  }

  return (
    <aside className="w-56 shrink-0 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      {/* 브랜드 */}
      <div className="px-4 py-4 border-b border-gray-100">
        <a href="/projects" className="text-sm font-bold text-gray-900 hover:text-blue-700">
          사내 RAG 플랫폼
        </a>
      </div>

      {/* 프로젝트 목록 */}
      <nav className="flex-1 overflow-y-auto py-2">
        <p className="px-4 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          프로젝트
        </p>
        {projects.map((project) => {
          const isExpanded = expandedSlug === project.slug;
          const isCurrent = currentSlug === project.slug;

          const subItems = [
            { href: `/chat?project=${project.slug}`, basePath: "/chat", label: "💬 AI 대화" },
            { href: `/documents?project=${project.slug}`, basePath: "/documents", label: "📄 문서" },
            ...(project.source_config?.enabled
              ? [{ href: `/source?project=${project.slug}`, basePath: "/source", label: "💻 소스코드" }]
              : []),
            ...(hasPlugin(project, "proposal")
              ? [{ href: `/proposals?project=${project.slug}`, basePath: "/proposals", label: "📝 제안서 초안" }]
              : []),
          ];

          return (
            <div key={project.slug}>
              <button
                onClick={() => {
                  if (isExpanded) {
                    setExpandedSlug(null);
                  } else {
                    setExpandedSlug(project.slug);
                    router.push(`/chat?project=${project.slug}`);
                  }
                }}
                className={`w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-gray-50 transition-colors ${
                  isCurrent ? "text-blue-700 font-medium" : "text-gray-700"
                }`}
              >
                <span className="truncate">{project.name}</span>
                <span className="text-gray-400 ml-1 text-xs">{isExpanded ? "▾" : "▸"}</span>
              </button>

              {isExpanded && (
                <div className="pl-3 pb-1">
                  {subItems.map((item) => (
                    <a
                      key={item.href}
                      href={item.href}
                      className={`block px-3 py-1.5 text-sm rounded-md transition-colors ${
                        isItemActive(item.basePath, project.slug)
                          ? "bg-blue-50 text-blue-700 font-medium"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                      }`}
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* 하단 */}
      <div className="border-t border-gray-100 py-2">
        <a
          href="/admin/projects"
          className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
            pathname.startsWith("/admin")
              ? "text-blue-700 font-medium bg-blue-50"
              : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
          }`}
        >
          <span>⚙️</span> 프로젝트 관리
        </a>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-500 hover:bg-red-50 text-left transition-colors"
        >
          <span>→</span> 로그아웃
        </button>
      </div>
    </aside>
  );
}
