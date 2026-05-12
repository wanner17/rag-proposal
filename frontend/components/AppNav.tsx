"use client";

import { useRouter } from "next/navigation";

import { navigationItems } from "@/lib/plugins";

export default function AppNav({
  className = "flex gap-3 text-sm",
  linkClassName = "text-gray-500 hover:text-gray-700",
  logoutClassName = "text-red-500 hover:text-red-700",
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
