// Тонкий клиент к /api/v1: cookie-сессия Django + CSRF-токен в заголовке.

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(extractMessage(data) ?? `HTTP ${status}`);
  }
}

function extractMessage(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (d.error && typeof d.error === "object") return String((d.error as Record<string, unknown>).message);
  if (typeof d.detail === "string") return d.detail;
  // Ошибки валидации DRF: { field: ["сообщение"] } или { field: { nested: [...] } }
  const first = Object.values(d)[0];
  if (Array.isArray(first)) return String(first[0]);
  if (typeof first === "string") return first;
  if (first && typeof first === "object") return extractMessage(first);
  return null;
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrf(): Promise<string> {
  let token = getCookie("csrftoken");
  if (!token) {
    await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
    token = getCookie("csrftoken");
  }
  return token ?? "";
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["X-CSRFToken"] = await ensureCsrf();
    headers["Content-Type"] = "application/json";
  }
  try {
    const lang = localStorage.getItem("lang");
    if (lang) headers["Accept-Language"] = lang;
  } catch {
    /* localStorage недоступен — язык по умолчанию */
  }

  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}
