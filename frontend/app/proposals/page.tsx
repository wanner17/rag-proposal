import ProposalPage from "@/plugins/proposal/pages/ProposalPage";
import { isPluginEnabled } from "@/lib/plugins";

export default function ProposalsRoute() {
  if (!isPluginEnabled("proposal")) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <section className="w-full max-w-lg rounded-2xl border bg-white p-6 text-center shadow-sm">
          <h1 className="text-xl font-semibold">비활성화된 플러그인입니다</h1>
          <p className="mt-2 text-sm text-gray-600">
            proposal 플러그인이 현재 빌드 설정에서 활성화되어 있지 않습니다.
          </p>
        </section>
      </main>
    );
  }

  return <ProposalPage />;
}
