import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

async function proxy(req: NextRequest, method: "GET" | "POST") {
  const auth = req.headers.get("authorization") ?? "";
  const body = method === "POST" ? await req.text() : undefined;
  const res = await fetch(`${BACKEND}/api/projects`, {
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

export async function GET(req: NextRequest) {
  return proxy(req, "GET");
}

export async function POST(req: NextRequest) {
  return proxy(req, "POST");
}
