import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8088";

export async function GET(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  const res = await fetch(`${BACKEND}/api/documents`, {
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
