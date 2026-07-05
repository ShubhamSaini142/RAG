"use client";

import * as React from "react";
import { CheckCircle2, KeyRound, Cpu, Sparkles } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/ui/page";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CenteredSpinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ProviderConfig, ProviderKind, ProvidersResponse } from "@/lib/types";

const LLM_PROVIDERS = ["openai", "anthropic", "gemini", "openai_compatible"];
const EMBEDDING_PROVIDERS = ["openai", "gemini", "openai_compatible"];

const MODEL_HINTS: Record<string, { llm?: string; embedding?: string }> = {
  openai: { llm: "gpt-4o-mini", embedding: "text-embedding-3-small" },
  anthropic: { llm: "claude-sonnet-4-6" },
  gemini: { llm: "gemini-1.5-flash", embedding: "text-embedding-004" },
  openai_compatible: { llm: "e.g. llama3.1", embedding: "e.g. nomic-embed-text" },
};

function ProviderForm({
  kind,
  current,
  onSaved,
}: {
  kind: ProviderKind;
  current: ProviderConfig | null;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const providerOptions = kind === "llm" ? LLM_PROVIDERS : EMBEDDING_PROVIDERS;

  const [provider, setProvider] = React.useState(current?.provider ?? providerOptions[0]);
  const [model, setModel] = React.useState(current?.model ?? "");
  const [apiKey, setApiKey] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState(current?.base_url ?? "");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const needsBaseUrl = provider === "openai_compatible";
  const modelHint = MODEL_HINTS[provider]?.[kind];

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!apiKey.trim()) {
      setError("Enter an API key to save.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        provider,
        model: model.trim(),
        api_key: apiKey.trim(),
        base_url: needsBaseUrl ? baseUrl.trim() : null,
      };
      if (kind === "llm") await api.setLLMProvider(body);
      else await api.setEmbeddingProvider(body);
      setApiKey("");
      toast(`${kind === "llm" ? "Chat model" : "Embedding"} provider saved.`, "success");
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save provider.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Provider">
          <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providerOptions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Model" hint={modelHint ? `e.g. ${modelHint}` : undefined}>
          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={modelHint}
            required
          />
        </Field>
      </div>

      {needsBaseUrl && (
        <Field label="Base URL" hint="Required for OpenAI-compatible endpoints (Ollama / vLLM / OpenRouter).">
          <Input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1"
            required
          />
        </Field>
      )}

      <Field
        label="API key"
        hint={
          current?.api_key_masked
            ? `Currently set (${current.api_key_masked}). Enter a new key to replace it.`
            : "Stored encrypted. Never shown again after saving."
        }
      >
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={current?.api_key_masked ?? "sk-…"}
          autoComplete="off"
        />
      </Field>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Button type="submit" loading={saving}>
        <KeyRound className="h-4 w-4" />
        {current?.configured ? "Update provider" : "Save provider"}
      </Button>
    </form>
  );
}

function ProviderCard({
  kind,
  icon,
  title,
  description,
  current,
  onSaved,
  canEdit,
}: {
  kind: ProviderKind;
  icon: React.ReactNode;
  title: string;
  description: string;
  current: ProviderConfig | null;
  onSaved: () => void;
  canEdit: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
              {icon}
            </span>
            <div>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </div>
          </div>
          {current?.configured ? (
            <Badge tone="success">
              <CheckCircle2 className="h-3.5 w-3.5" /> Configured
            </Badge>
          ) : (
            <Badge tone="warning">Not set</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {current?.configured && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-muted p-3 text-sm sm:grid-cols-4">
            <Meta label="Provider" value={current.provider} />
            <Meta label="Model" value={current.model} />
            <Meta label="Key" value={current.api_key_masked ?? "—"} />
            {kind === "embedding" && (
              <Meta label="Dimension" value={current.embedding_dim?.toString() ?? "—"} />
            )}
          </dl>
        )}
        {canEdit ? (
          <ProviderForm kind={kind} current={current} onSaved={onSaved} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Only owners and admins can change providers.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium text-foreground">{value}</dd>
    </div>
  );
}

export default function SettingsPage() {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const [data, setData] = React.useState<ProvidersResponse | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    try {
      setData(await api.getProviders());
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to load settings.", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <PageContainer>
      <PageHeader
        title="AI Providers"
        description="Bring your own model keys. Configure an embedding model and a chat model before uploading or asking."
      />

      <div className="mt-8 space-y-6">
        {loading ? (
          <CenteredSpinner label="Loading providers…" />
        ) : (
          <>
            <ProviderCard
              kind="embedding"
              icon={<Sparkles className="h-5 w-5" />}
              title="Embedding model"
              description="Turns your documents into vectors. Sets the search dimension."
              current={data?.embedding ?? null}
              onSaved={load}
              canEdit={isAdmin}
            />
            <ProviderCard
              kind="llm"
              icon={<Cpu className="h-5 w-5" />}
              title="Chat model"
              description="Generates answers grounded in retrieved context."
              current={data?.llm ?? null}
              onSaved={load}
              canEdit={isAdmin}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
