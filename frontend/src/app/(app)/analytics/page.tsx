"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Coins, FileText, MessagesSquare } from "lucide-react";
import { PageContainer, PageHeader, EmptyState } from "@/components/ui/page";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { CenteredSpinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { Analytics } from "@/lib/types";

type Scope = "me" | "org";

function fmt(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function AnalyticsPage() {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const [scope, setScope] = React.useState<Scope>("me");
  const [data, setData] = React.useState<Analytics | null>(null);
  const [loading, setLoading] = React.useState(true);

  // Admins default to the org-wide view.
  React.useEffect(() => {
    if (isAdmin) setScope("org");
  }, [isAdmin]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (scope === "org" ? api.getOrgAnalytics() : api.getMyAnalytics())
      .then((d) => !cancelled && setData(d))
      .catch((err) => {
        if (cancelled) return;
        toast(err instanceof ApiError ? err.message : "Failed to load analytics.", "error");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [scope, toast]);

  const totals = data?.totals;
  const hasUsage = (totals?.requests ?? 0) > 0;

  return (
    <PageContainer>
      <PageHeader
        title="Analytics"
        description={
          scope === "org"
            ? "Token usage and activity across your whole organization."
            : "Your own token usage and activity."
        }
        actions={
          isAdmin ? (
            <div className="flex rounded-lg border border-border bg-card p-0.5">
              {(["org", "me"] as Scope[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setScope(s)}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    scope === s
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {s === "org" ? "Organization" : "Just me"}
                </button>
              ))}
            </div>
          ) : undefined
        }
      />

      {loading ? (
        <CenteredSpinner label="Loading analytics…" />
      ) : !data ? null : (
        <div className="mt-8 space-y-6">
          {/* Stat tiles */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat
              label="Total tokens"
              value={fmt(totals!.total_tokens)}
              sublabel={`${fmt(totals!.input_tokens)} in · ${fmt(totals!.output_tokens)} out`}
              icon={<Coins className="h-4 w-4" />}
            />
            <Stat
              label="Chat requests"
              value={fmt(totals!.requests)}
              icon={<Activity className="h-4 w-4" />}
            />
            <Stat
              label="Documents"
              value={fmt(totals!.documents)}
              icon={<FileText className="h-4 w-4" />}
            />
            <Stat
              label="Conversations"
              value={fmt(totals!.conversations)}
              icon={<MessagesSquare className="h-4 w-4" />}
            />
          </div>

          {!hasUsage ? (
            <EmptyState
              icon={<Activity className="h-6 w-6" />}
              title="No usage yet"
              description="Once you ask questions in Chat, token usage and trends will appear here."
            />
          ) : (
            <>
              {/* Tokens over time */}
              <Card>
                <CardHeader>
                  <CardTitle>Tokens over time</CardTitle>
                  <CardDescription>Input and output tokens per day (last 30 days).</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="fillInput" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
                          </linearGradient>
                          <linearGradient id="fillOutput" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.35} />
                            <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="date"
                          tickFormatter={shortDate}
                          stroke="var(--chart-axis)"
                          tick={{ fontSize: 12, fill: "var(--chart-axis)" }}
                          tickLine={false}
                          axisLine={{ stroke: "var(--chart-grid)" }}
                        />
                        <YAxis
                          tickFormatter={fmt}
                          stroke="var(--chart-axis)"
                          tick={{ fontSize: 12, fill: "var(--chart-axis)" }}
                          tickLine={false}
                          axisLine={false}
                          width={44}
                        />
                        <Tooltip content={<UsageTooltip />} />
                        <Legend
                          iconType="circle"
                          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                        />
                        <Area
                          type="monotone"
                          dataKey="input_tokens"
                          name="Input"
                          stackId="1"
                          stroke="var(--chart-1)"
                          strokeWidth={2}
                          fill="url(#fillInput)"
                        />
                        <Area
                          type="monotone"
                          dataKey="output_tokens"
                          name="Output"
                          stackId="1"
                          stroke="var(--chart-2)"
                          strokeWidth={2}
                          fill="url(#fillOutput)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* By model */}
              <Card>
                <CardHeader>
                  <CardTitle>Tokens by model</CardTitle>
                  <CardDescription>Total tokens per provider / model.</CardDescription>
                </CardHeader>
                <CardContent>
                  <HBarChart
                    rows={data.by_model.map((m) => ({
                      label: m.model,
                      sub: m.provider,
                      value: m.total_tokens,
                      requests: m.requests,
                    }))}
                  />
                </CardContent>
              </Card>

              {/* By user (org scope only) */}
              {scope === "org" && data.by_user && data.by_user.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Tokens by user</CardTitle>
                    <CardDescription>Who is using the knowledge base most.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <HBarChart
                      rows={data.by_user.map((u) => ({
                        label: u.name || u.email,
                        sub: u.email,
                        value: u.total_tokens,
                        requests: u.requests,
                      }))}
                    />
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}
    </PageContainer>
  );
}

/* ---------- horizontal bar chart (single magnitude series) ---------- */

interface BarRow {
  label: string;
  sub?: string;
  value: number;
  requests?: number;
}

function HBarChart({ rows }: { rows: BarRow[] }) {
  const height = Math.max(120, rows.length * 46 + 16);
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={fmt}
            stroke="var(--chart-axis)"
            tick={{ fontSize: 12, fill: "var(--chart-axis)" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={132}
            stroke="var(--chart-axis)"
            tick={{ fontSize: 12, fill: "var(--chart-axis)" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<BarTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
          <Bar dataKey="value" name="Tokens" fill="var(--chart-1)" radius={[0, 4, 4, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------- custom tooltips (theme-aware) ---------- */

interface TipEntry {
  name?: string;
  value?: number;
  color?: string;
  payload?: Record<string, unknown>;
}

function TooltipShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg">
      {children}
    </div>
  );
}

function UsageTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TipEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value ?? 0), 0);
  return (
    <TooltipShell>
      <p className="mb-1 font-medium text-foreground">{shortDate(label ?? "")}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 text-muted-foreground">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="tabular-nums text-foreground">{fmt(p.value ?? 0)}</span>
        </p>
      ))}
      <p className="mt-1 border-t border-border pt-1 text-muted-foreground">
        Total: <span className="tabular-nums font-medium text-foreground">{fmt(total)}</span>
      </p>
    </TooltipShell>
  );
}

function BarTooltip({ active, payload }: { active?: boolean; payload?: TipEntry[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as unknown as BarRow;
  return (
    <TooltipShell>
      <p className="font-medium text-foreground">{row.label}</p>
      {row.sub && <p className="text-muted-foreground">{row.sub}</p>}
      <p className="mt-1 text-muted-foreground">
        <span className="tabular-nums font-medium text-foreground">{fmt(row.value)}</span> tokens
        {typeof row.requests === "number" ? ` · ${fmt(row.requests)} requests` : ""}
      </p>
    </TooltipShell>
  );
}
