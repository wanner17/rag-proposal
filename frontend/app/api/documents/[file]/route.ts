import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ file: string }> }
) {
  const auth = req.headers.get("authorization") ?? "";
  const { file } = await params;
  const projectId = req.nextUrl.searchParams.get("project_id");
  const backendUrl = projectId
    ? `${BACKEND}/api/documents/${encodeURIComponent(file)}?project_id=${encodeURIComponent(projectId)}`
    : `${BACKEND}/api/documents/${encodeURIComponent(file)}`;
  const res = await fetch(backendUrl, {
    method: "DELETE",
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
