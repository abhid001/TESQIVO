// Typed API client. Every mutating call carries the CSRF double-submit token
// (decision D-011) and the web-client marker. Errors surface as ApiError with the
// PRS §13 envelope fields.

const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface ApiErrorBody {
  code: string;
  message: string;
  status: number;
  correlation_id: string;
  details: { field: string; code: string; message: string }[];
  retryable: boolean;
}

export class ApiError extends Error {
  body: ApiErrorBody;
  constructor(body: ApiErrorBody) {
    super(body.message);
    this.body = body;
  }
}

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : null;
}

type Options = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  raw?: boolean;
  signal?: AbortSignal;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {
    "X-Tesqivo-Client": "web",
    ...(opts.headers ?? {}),
  };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("tesqivo_csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const res = await fetch(BASE + path, {
    method,
    headers,
    credentials: "same-origin",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(
      data?.error ?? {
        code: "UNKNOWN",
        message: `Request failed (${res.status})`,
        status: res.status,
        correlation_id: res.headers.get("x-correlation-id") ?? "",
        details: [],
        retryable: false,
      },
    );
  }
  return data as T;
}

/** POST a JSON body and read a Server-Sent Events reply, one parsed `data:` payload
 *  at a time. Errors before the stream starts throw ApiError like `api()` does. */
export async function streamEvents<E>(
  path: string,
  body: unknown,
  onEvent: (event: E) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await api<Response>(path, { method: "POST", body, raw: true, signal });
  if (!res.ok) {
    const text = await res.text();
    const data = text ? JSON.parse(text) : undefined;
    throw new ApiError(
      data?.error ?? {
        code: "UNKNOWN", message: `Request failed (${res.status})`, status: res.status,
        correlation_id: res.headers.get("x-correlation-id") ?? "", details: [], retryable: false,
      },
    );
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      for (const line of frame.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as E);
      }
    }
  }
}

export const http = {
  get: <T>(p: string) => api<T>(p),
  post: <T>(p: string, body?: unknown) => api<T>(p, { method: "POST", body }),
  patch: <T>(p: string, body?: unknown) => api<T>(p, { method: "PATCH", body }),
  put: <T>(p: string, body?: unknown) => api<T>(p, { method: "PUT", body }),
  del: <T>(p: string) => api<T>(p, { method: "DELETE" }),
};
