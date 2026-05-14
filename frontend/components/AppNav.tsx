"use client";

import { useRouter } from "next/navigation";

import { navigationItems } from "@/lib/plugins";

export default function AppNav({
  className = "flex items-center gap-4 text-sm font-medium",
  linkClassName = "text-gray-600 transition-colors hover:text-gray-900",
  logoutClassName = "text-red-600 transition-colors hover:text-red-800",
}: {
  className?: string;
  linkClassName?: string;
  logoutClassName?: string;
}) {
  const router = useRouter();

  function handleLogout() {
    localStorage.removeItem("token");
    router.push("/login");
  }

  return (
    <nav className={className}>
      {navigationItems.map((item) => (
        <a key={item.href} href={item.href} className={linkClassName}>
          {item.label}
        </a>
      ))}
      <button onClick={handleLogout} className={logoutClassName}>
        로그아웃
      </button>
    </nav>
  );
}
