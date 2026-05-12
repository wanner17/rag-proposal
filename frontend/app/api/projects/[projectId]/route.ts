import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

async function proxy(
  req: NextRequest,
  context: { params: Promise<{ projectId: string }> },
  method: "GET" | "PATCH"
) {
  const { projectId } = await context.params;
  const auth = req.headers.get("authorization") ?? "";
  const body = method === "PATCH" ? await req.text() : undefined;
  const res = await fetch(`${BACKEND}/api/projects/${encodeURIComponent(projectId)}`, {
    method,
    headers: {
      authorization: auth,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
    },
  });
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  return proxy(req, context, "GET");
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  return proxy(req, context, "PATCH");
}
