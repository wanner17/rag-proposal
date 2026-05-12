import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const auth = req.headers.get("authorization") ?? "";
  const res = await fetch(`${BACKEND}/api/projects/${encodeURIComponent(projectId)}/export`, {
    headers: { authorization: auth },
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "text/yaml",
      "content-disposition": res.headers.get("content-disposition") ?? "",
    },
  });
}
