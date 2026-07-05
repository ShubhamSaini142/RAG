"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUp, MessageSquareText, Square, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { streamChat } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Citation } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  pending?: boolean;
  error?: boolean;
}

const SUGGESTIONS = [
  "Summarize my documents.",
  "What are the key points?",
  "What does it say about pricing?",
];

let msgId = 0;
const nextId = () => `m${++msgId}`;

export default function ChatPage() {
  const { toast } = useToast();
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [streaming, setStreaming] = React.useState(false);
  const conversationId = React.useRef<string | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const update = (id: string, patch: Partial<Message>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));

  async function send(question: string) {
    const q = question.trim();
    if (!q || streaming) return;

    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: q },
      { id: assistantId, role: "assistant", content: "", pending: true },
    ]);
    setInput("");
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    await streamChat(
      { question: q, conversation_id: conversationId.current, top_k: 5 },
      {
        onCitations: (citations) => update(assistantId, { citations }),
        onToken: (text) =>
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + text, pending: false }
                : m,
            ),
          ),
        onDone: (cid) => {
          conversationId.current = cid;
          update(assistantId, { pending: false });
        },
        onError: (message) => {
          update(assistantId, {
            pending: false,
            error: true,
            content: message,
          });
          toast(message, "error");
        },
      },
      controller.signal,
    );

    setStreaming(false);
    abortRef.current = null;
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
          {empty ? (
            <div className="flex flex-col items-center pt-16 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <MessageSquareText className="h-7 w-7" />
              </div>
              <h1 className="text-xl font-semibold text-foreground">Ask your knowledge base</h1>
              <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
                Answers are grounded in your uploaded documents, with citations. Make sure
                you&apos;ve{" "}
                <Link href="/documents" className="text-primary hover:underline">
                  uploaded a document
                </Link>{" "}
                first.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-border bg-card px-3.5 py-1.5 text-sm text-muted-foreground transition-colors hover:border-input hover:text-foreground"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((m) => (
                <MessageView key={m.id} message={m} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-background/80 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl px-4 py-4 sm:px-6">
          <div className="relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask a question…"
              className="max-h-40 pr-14"
            />
            <div className="absolute bottom-2 right-2">
              {streaming ? (
                <Button size="icon" variant="secondary" onClick={stop} aria-label="Stop">
                  <Square className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  onClick={() => send(input)}
                  disabled={!input.trim()}
                  aria-label="Send"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Enter to send · Shift+Enter for a new line
          </p>
        </div>
      </div>
    </div>
  );
}

function MessageView({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%] space-y-3", isUser && "flex flex-col items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
            isUser
              ? "bg-primary text-primary-foreground"
              : message.error
                ? "bg-destructive/10 text-destructive"
                : "bg-card border border-border text-card-foreground",
          )}
        >
          {message.pending && !message.content ? (
            <span className="inline-flex gap-1">
              <Dot /> <Dot delay="0.15s" /> <Dot delay="0.3s" />
            </span>
          ) : (
            message.content
          )}
        </div>
        {message.citations && message.citations.length > 0 && (
          <Citations citations={message.citations} />
        )}
      </div>
    </div>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  return (
    <div className="w-full space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">Sources</p>
      <div className="grid gap-1.5">
        {citations.map((c) => (
          <div
            key={c.chunk_id}
            className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-2.5 text-xs"
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-accent-foreground">
              {c.n}
            </span>
            <div className="min-w-0">
              <p className="line-clamp-2 text-muted-foreground">{c.snippet}</p>
              <p className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground/70">
                <FileText className="h-3 w-3" />
                doc {c.document_id.slice(0, 8)} · score {c.score.toFixed(2)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Dot({ delay = "0s" }: { delay?: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground"
      style={{ animationDelay: delay }}
    />
  );
}
