"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import AppSidebar from "./AppSidebar";

const NO_SIDEBAR_PATHS = ["/login"];

function SidebarWrapper() {
  const pathname = usePathname();
  const hideSidebar = NO_SIDEBAR_PATHS.some((p) => pathname.startsWith(p));
  if (hideSidebar) return null;
  return <AppSidebar />;
}

export default function SidebarLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideSidebar = NO_SIDEBAR_PATHS.some((p) => pathname.startsWith(p));

  if (hideSidebar) return <>{children}</>;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Suspense fallback={<div className="w-56 shrink-0 min-h-screen bg-white border-r border-gray-200" />}>
        <SidebarWrapper />
      </Suspense>
      <main className="flex-1 min-w-0 overflow-auto">{children}</main>
    </div>
  );
}
