import { proposalPlugin } from "@/plugins/proposal/plugin";

export interface NavigationItem {
  href: string;
  label: string;
  order: number;
}

const coreNavigation: NavigationItem[] = [
  { href: "/chat", label: "채팅", order: 10 },
  { href: "/documents", label: "문서 조회", order: 20 },
  { href: "/upload", label: "문서 업로드", order: 40 },
];

const enabledPluginIds = (
  process.env.NEXT_PUBLIC_RAG_ENABLED_PLUGINS ??
  process.env.RAG_ENABLED_PLUGINS ??
  "proposal"
)
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean);

export function isPluginEnabled(pluginId: string) {
  return enabledPluginIds.includes(pluginId);
}

const pluginNavigation: NavigationItem[] = isPluginEnabled(proposalPlugin.id)
  ? [
      {
        href: proposalPlugin.route,
        label: proposalPlugin.navigation.label,
        order: proposalPlugin.navigation.order,
      },
    ]
  : [];

export const navigationItems = [...coreNavigation, ...pluginNavigation].sort(
  (a, b) => a.order - b.order
);
