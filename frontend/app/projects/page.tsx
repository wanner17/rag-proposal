"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listProjects, type Project } from "@/lib/projects";

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    listProjects(token)
      .then((list) => setProjects(list.filter((p) => p.status === "active")))
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        불러오는 중...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">프로젝트</h1>
      <p className="text-sm text-gray-500 mb-8">검색하고 싶은 지식베이스를 선택하세요.</p>

      {projects.length === 0 ? (
        <div className="text-sm text-gray-400">
          등록된 프로젝트가 없습니다.{" "}
          <a href="/admin/projects" className="text-blue-600 underline">
            프로젝트 관리
          </a>
          에서 추가하세요.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const hasSource = project.source_config?.enabled;

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      <div>
        <h2 className="font-semibold text-gray-900 truncate">{project.name}</h2>
        {project.description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">{project.description}</p>
        )}
      </div>

      <div className="flex gap-1.5 flex-wrap text-xs text-gray-400">
        <span className="bg-gray-100 rounded px-2 py-0.5">📄 문서</span>
        {hasSource && <span className="bg-gray-100 rounded px-2 py-0.5">💻 소스코드</span>}
      </div>

      <a
        href={`/chat?project=${project.slug}`}
        className="mt-auto block text-center bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
      >
        대화하기
      </a>
    </div>
  );
}
