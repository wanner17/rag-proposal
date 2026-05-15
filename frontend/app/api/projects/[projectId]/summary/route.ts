import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

type Context = { params: Promise<{ projectId: string }> };

export async function GET(req: NextRequest, context: Context) {
  const { projectId } = await context.params;
  const auth = req.headers.get("authorization") ?? "";
  const res = await fetch(`${BACKEND}/api/projects/${encodeURIComponent(projectId)}/summary`, {
    headers: { authorization: auth },
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function PUT(req: NextRequest, context: Context) {
  const { projectId } = await context.params;
  const auth = req.headers.get("authorization") ?? "";
  const body = await req.text();
  const res = await fetch(`${BACKEND}/api/projects/${encodeURIComponent(projectId)}/summary`, {
    method: "PUT",
    headers: { authorization: auth, "content-type": "application/json" },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
