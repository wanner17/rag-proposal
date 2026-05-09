import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8088";

export async function POST(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  const contentType = req.headers.get("content-type") ?? "";

  const body = await req.arrayBuffer();

  const res = await fetch(`${BACKEND}/api/ingest`, {
    method: "POST",
    headers: {
      authorization: auth,
      "content-type": contentType,
    },
    body,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
