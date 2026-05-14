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
    <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white min-h-screen shadow-sm">
      {/* 브랜드 */}
      <div className="flex h-16 shrink-0 items-center border-b border-gray-200 px-6">
        <a href="/projects" className="text-lg font-bold tracking-tight text-gray-900 transition-colors hover:text-blue-600">
          사내 RAG 플랫폼
        </a>
      </div>

      {/* 프로젝트 목록 */}
      <nav className="flex-1 overflow-y-auto py-4">
        <p className="mb-2 px-6 text-xs font-semibold uppercase tracking-wider text-gray-500">
          내 프로젝트
        </p>
        {projects.map((project) => {
          const isExpanded = expandedSlug === project.slug;
          const isCurrent = currentSlug === project.slug;

          const subItems = [
            { href: `/chat?project=${project.slug}`, basePath: "/chat", label: "💬 AI 대화" },
            { href: `/documents?project=${project.slug}`, basePath: "/documents", label: "📄 문서 검색" },
            { href: `/upload?project=${project.slug}`, basePath: "/upload", label: "📤 문서 업로드" },
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
                className={`group flex w-full items-center justify-between px-6 py-2.5 text-left text-sm font-medium transition-colors ${
                  isCurrent ? "bg-blue-50/50 text-blue-600" : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <span className="truncate">{project.name}</span>
                <span className={`ml-1 text-xs transition-transform ${isExpanded ? "text-blue-600" : "text-gray-400 group-hover:text-gray-600"}`}>
                  {isExpanded ? "▾" : "▸"}
                </span>
              </button>

              {isExpanded && (
                <div className="space-y-1 pb-2 pl-6 pr-4 pt-1">
                  {subItems.map((item) => {
                    const active = isItemActive(item.basePath, project.slug);
                    return (
                      <a
                        key={item.href}
                        href={item.href}
                        className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                          active
                            ? "bg-blue-50 font-semibold text-blue-700 ring-1 ring-inset ring-blue-700/10"
                            : "font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                        }`}
                      >
                        {item.label}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* 하단 */}
      <div className="space-y-1 border-t border-gray-200 p-4">
        <a
          href="/admin/projects"
          className={`flex items-center gap-x-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
            pathname.startsWith("/admin")
              ? "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-700/10"
              : "text-gray-700 hover:bg-gray-50 hover:text-gray-900"
          }`}
        >
          <span className="text-base">⚙️</span> 프로젝트 관리
        </a>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-x-3 rounded-md px-3 py-2 text-left text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
        >
          <span className="text-base text-red-500">→</span> 로그아웃
        </button>
      </div>
    </aside>
  );
}
