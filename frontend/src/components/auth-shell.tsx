import Link from "next/link";
import { Brand } from "./brand";
import { FileText, MessageSquareText, ShieldCheck } from "lucide-react";

const points = [
  { icon: FileText, text: "Upload documents — indexed and searchable in seconds." },
  { icon: MessageSquareText, text: "Ask questions, get answers grounded in your content with citations." },
  { icon: ShieldCheck, text: "Bring your own model keys. Encrypted, isolated per organization." },
];

/** Two-pane auth layout: brand story on the left, form on the right. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-primary p-12 text-primary-foreground lg:flex lg:flex-col lg:justify-between">
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.35), transparent 45%), radial-gradient(circle at 80% 70%, rgba(255,255,255,0.25), transparent 40%)",
          }}
        />
        <Link href="/" className="relative">
          <Brand className="[&_span:last-child]:text-primary-foreground" />
        </Link>
        <div className="relative space-y-8">
          <h2 className="max-w-md text-3xl font-semibold leading-tight">
            Your knowledge base, answered with citations.
          </h2>
          <ul className="space-y-4">
            {points.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-sm text-primary-foreground/90">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-primary-foreground/70">
          Multi-tenant RAG · OpenAI · Anthropic · Gemini · self-hosted models
        </p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Brand />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>
        </div>
      </div>
    </div>
  );
}
