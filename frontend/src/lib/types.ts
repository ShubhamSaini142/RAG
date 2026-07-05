// Types mirroring the FastAPI backend responses (see docs/api-reference.md).

export type Role = "owner" | "admin" | "editor" | "viewer";

export interface AuthResponse {
  access_token: string;
  token_type: string;
  org_id: string;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
}

export interface Org {
  id: string;
  name: string;
  plan: string;
  role: Role;
}

export interface Me {
  user: User;
  orgs: Org[];
}

export type ProviderKind = "llm" | "embedding";
export type LLMProviderName = "openai" | "anthropic" | "gemini" | "openai_compatible";
export type EmbeddingProviderName = "openai" | "gemini" | "openai_compatible";

export interface ProviderConfig {
  kind: ProviderKind;
  provider: string;
  model: string;
  base_url: string | null;
  embedding_dim: number | null;
  api_key_masked: string | null;
  configured: boolean;
}

export interface ProvidersResponse {
  llm: ProviderConfig | null;
  embedding: ProviderConfig | null;
}

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export interface Document {
  id: string;
  filename: string;
  source_type: string;
  status: DocumentStatus;
  error_msg: string | null;
}

export interface Citation {
  n: number;
  chunk_id: string;
  document_id: string;
  snippet: string;
  score: number;
}

/* ---- analytics ---- */

export interface UsageTotals {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  requests: number;
  documents: number;
  conversations: number;
}

export interface DailyUsage {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  requests: number;
}

export interface ModelUsage {
  provider: string;
  model: string;
  total_tokens: number;
  requests: number;
}

export interface UserUsage {
  user_id: string | null;
  email: string;
  name: string | null;
  total_tokens: number;
  requests: number;
}

export interface Analytics {
  scope: "me" | "org";
  totals: UsageTotals;
  daily: DailyUsage[];
  by_model: ModelUsage[];
  by_user?: UserUsage[];
}
