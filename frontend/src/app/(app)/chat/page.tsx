"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowUp,
  FileText,
  MessagesSquare,
  Plus,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, streamChat } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Citation, ConversationSummary } from "@/lib/types";

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
  const [conversations, setConversations] = React.useState<ConversationSummary[] | null>(null);
  const [conversationId, setConversationId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [streaming, setStreaming] = React.useState(false);
  const [loadingConv, setLoadingConv] = React.useState(false);
  const [listOpen, setListOpen] = React.useState(false); // mobile drawer
  const abortRef = React.useRef<AbortController | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadConversations = React.useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch {
      setConversations([]);
    }
  }, []);

  React.useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const update = (id: string, patch: Partial<Message>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }

  function newChat() {
    stop();
    setMessages([]);
    setConversationId(null);
    setInput("");
    setListOpen(false);
  }

  async function openConversation(id: string) {
    if (streaming) stop();
    setListOpen(false);
    setConversationId(id);
    setLoadingConv(true);
    try {
      const detail = await api.getConversation(id);
      setMessages(
        detail.messages.map((m) => ({
          id: nextId(),
          role: m.role,
          content: m.content,
          citations: m.citations?.length ? m.citations : undefined,
        })),
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn't open that conversation.", "error");
    } finally {
      setLoadingConv(false);
    }
  }

  async function removeConversation(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev?.filter((c) => c.id !== id) ?? null);
      if (conversationId === id) newChat();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Delete failed.", "error");
    }
  }

  async function send(question: string) {
    const q = question.trim();
    if (!q || streaming) return;

    const wasNew = conversationId === null;
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

    // Hold citations back until the answer finishes — sources appear after the
    // answer, not before it.
    let captured: Citation[] | undefined;

    await streamChat(
      { question: q, conversation_id: conversationId, top_k: 5 },
      {
        onCitations: (citations) => {
          captured = citations;
        },
        onToken: (text) =>
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + text, pending: false }
                : m,
            ),
          ),
        onDone: (cid) => {
          if (cid) setConversationId(cid);
          update(assistantId, {
            pending: false,
            citations: captured?.length ? captured : undefined,
          });
          if (wasNew) loadConversations();
        },
        onError: (message) => {
          update(assistantId, { pending: false, error: true, content: message });
          toast(message, "error");
        },
      },
      controller.signal,
    );

    setStreaming(false);
    abortRef.current = null;
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const empty = messages.length === 0 && !loadingConv;

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Conversation sidebar (desktop) */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
        <ConversationPanel
          conversations={conversations}
          activeId={conversationId}
          onOpen={openConversation}
          onNew={newChat}
          onDelete={removeConversation}
        />
      </aside>

      {/* Conversation drawer (mobile) */}
      {listOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setListOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-72 border-r border-border bg-card shadow-xl animate-fade-in">
            <button
              onClick={() => setListOpen(false)}
              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
            <ConversationPanel
              conversations={conversations}
              activeId={conversationId}
              onOpen={openConversation}
              onNew={newChat}
              onDelete={removeConversation}
            />
          </div>
        </div>
      )}

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile chat header */}
        <div className="flex h-12 items-center justify-between border-b border-border px-4 md:hidden">
          <Button variant="ghost" size="sm" onClick={() => setListOpen(true)}>
            <MessagesSquare className="h-4 w-4" /> Chats
          </Button>
          <Button variant="ghost" size="sm" onClick={newChat}>
            <Plus className="h-4 w-4" /> New
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
            {loadingConv ? (
              <div className="flex justify-center pt-16">
                <Spinner />
              </div>
            ) : empty ? (
              <div className="flex flex-col items-center pt-16 text-center">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-accent-foreground">
                  <MessagesSquare className="h-7 w-7" />
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
    </div>
  );
}

/* ---------- conversation sidebar ---------- */

function ConversationPanel({
  conversations,
  activeId,
  onOpen,
  onNew,
  onDelete,
}: {
  conversations: ConversationSummary[] | null;
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNew}>
          <Plus className="h-4 w-4" /> New chat
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations === null ? (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        ) : conversations.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onOpen(c.id)}
                  className={cn(
                    "group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                    activeId === c.id
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <span className="flex-1 truncate">{c.title || "New conversation"}</span>
                  <span
                    role="button"
                    tabIndex={-1}
                    onClick={(e) => onDelete(c.id, e)}
                    className="opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ---------- messages ---------- */

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
              <p className="flex items-center gap-1 font-medium text-foreground">
                <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span className="truncate">
                  {c.document || `Document ${c.document_id.slice(0, 8)}`}
                </span>
              </p>
              <p className="mt-1 line-clamp-2 text-muted-foreground">{c.snippet}</p>
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
