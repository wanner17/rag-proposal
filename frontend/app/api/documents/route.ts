import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

export async function GET(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  const projectId = req.nextUrl.searchParams.get("project_id");
  const backendUrl = projectId
    ? `${BACKEND}/api/documents?project_id=${encodeURIComponent(projectId)}`
    : `${BACKEND}/api/documents`;
  const res = await fetch(backendUrl, {
    headers: { authorization: auth },
  });
  const text = await res.text();

  return new NextResponse(text, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
    },
  });
}
