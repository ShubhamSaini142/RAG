// Typed fetch client for the RAG backend.
// Base URL comes from NEXT_PUBLIC_API_URL (defaults to the local backend).

import type {
  Analytics,
  AuthResponse,
  Citation,
  ConversationDetail,
  ConversationSummary,
  Document,
  Me,
  Org,
  ProvidersResponse,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const TOKEN_KEY = "rag_token";

/* ---------- token storage ---------- */

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/* ---------- error type + 401 hook ---------- */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

let onUnauthorized: (() => void) | null = null;
/** AuthProvider registers a handler so a 401 anywhere logs the user out. */
export function registerUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

/* ---------- core request ---------- */

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** send raw body (e.g. FormData) without JSON-encoding */
  raw?: boolean;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, raw = false, auth = true } = opts;
  const headers: Record<string, string> = {};

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (raw) {
      payload = body as BodyInit;
    } else {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }

  if (res.status === 401 && auth) {
    clearToken();
    onUnauthorized?.();
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!res.ok) {
    throw new ApiError(res.status, await extractError(res));
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function extractError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
    return JSON.stringify(data);
  } catch {
    return res.statusText || `Request failed (${res.status})`;
  }
}

/* ---------- typed endpoints ---------- */

export const api = {
  register: (body: {
    email: string;
    password: string;
    name?: string;
    org_name?: string;
  }) => request<AuthResponse>("/auth/register", { method: "POST", body, auth: false }),

  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body, auth: false }),

  me: () => request<Me>("/auth/me"),

  listOrgs: () => request<Org[]>("/orgs"),

  createOrg: (body: { name: string }) =>
    request<Org>("/orgs", { method: "POST", body }),

  getProviders: () => request<ProvidersResponse>("/settings/providers"),

  setEmbeddingProvider: (body: {
    provider: string;
    model: string;
    api_key: string;
    base_url?: string | null;
  }) => request("/settings/providers/embedding", { method: "PUT", body }),

  setLLMProvider: (body: {
    provider: string;
    model: string;
    api_key: string;
    base_url?: string | null;
  }) => request("/settings/providers/llm", { method: "PUT", body }),

  listDocuments: () => request<Document[]>("/documents"),

  getDocument: (id: string) => request<Document>(`/documents/${id}`),

  deleteDocument: (id: string) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Document>("/documents", { method: "POST", body: form, raw: true });
  },

  getMyAnalytics: () => request<Analytics>("/analytics/me"),

  getOrgAnalytics: () => request<Analytics>("/analytics/org"),

  listConversations: () => request<ConversationSummary[]>("/conversations"),

  getConversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),
};

/* ---------- chat (SSE streaming) ---------- */

export interface ChatRequest {
  question: string;
  collection_id?: string | null;
  conversation_id?: string | null;
  top_k?: number;
}

export interface ChatCallbacks {
  onCitations?: (citations: Citation[]) => void;
  onToken?: (text: string) => void;
  onDone?: (conversationId: string | null) => void;
  onError?: (message: string) => void;
}

/**
 * POST /chat and consume the Server-Sent Events stream. We use fetch (not
 * EventSource) because the request needs an Authorization header and a JSON
 * body, and parse `event:`/`data:` frames manually.
 */
export async function streamChat(
  body: ChatRequest,
  callbacks: ChatCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") return;
    callbacks.onError?.("Cannot reach the server. Is the backend running?");
    return;
  }

  if (res.status === 401) {
    clearToken();
    onUnauthorized?.();
    callbacks.onError?.("Your session has expired. Please sign in again.");
    return;
  }
  if (!res.ok || !res.body) {
    callbacks.onError?.(await extractError(res));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) return;
    const data = dataLines.join("\n");
    try {
      if (event === "citations") callbacks.onCitations?.(JSON.parse(data));
      else if (event === "token") callbacks.onToken?.(JSON.parse(data).text ?? "");
      else if (event === "done")
        callbacks.onDone?.(JSON.parse(data).conversation_id ?? null);
      else if (event === "error") callbacks.onError?.(JSON.parse(data).detail ?? "Stream error.");
    } catch {
      /* ignore malformed frame */
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (frame.trim()) dispatch(frame);
      }
    }
    if (buffer.trim()) dispatch(buffer);
  } catch (err) {
    if ((err as Error)?.name !== "AbortError") {
      callbacks.onError?.("The connection was interrupted.");
    }
  }
}
