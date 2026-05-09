const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("로그인 실패");
  return res.json() as Promise<{ access_token: string }>;
}

export async function chatStream(
  query: string,
  token: string,
  onSource: (sources: Source[]) => void,
  onToken: (token: string) => void,
  onDone: () => void
) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) throw new Error("요청 실패");
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const lines = decoder.decode(value).split("\n");
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") { onDone(); return; }
      try {
        const data = JSON.parse(payload);
        if (data.sources) onSource(data.sources);
        if (data.token) onToken(data.token);
      } catch {}
    }
  }
  onDone();
}

export async function ingestDocument(formData: FormData, token: string) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) throw new Error("업로드 실패");
  return res.json();
}

export interface Source {
  file: string;
  page: number;
  section: string;
  score: number;
}
