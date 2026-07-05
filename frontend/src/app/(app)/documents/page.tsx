"use client";

import * as React from "react";
import Link from "next/link";
import { FileText, Trash2, UploadCloud } from "lucide-react";
import { PageContainer, PageHeader, EmptyState } from "@/components/ui/page";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CenteredSpinner } from "@/components/ui/spinner";
import { DocStatusBadge } from "@/components/doc-status-badge";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Document } from "@/lib/types";

const ACCEPTED = [".txt", ".md"];
const MAX_BYTES = 10 * 1024 * 1024;

function isActive(status: string) {
  return status === "queued" || status === "processing";
}

export default function DocumentsPage() {
  const { toast } = useToast();
  const [docs, setDocs] = React.useState<Document[] | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [dragging, setDragging] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    try {
      setDocs(await api.listDocuments());
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to load documents.", "error");
    }
  }, [toast]);

  React.useEffect(() => {
    load();
  }, [load]);

  // Poll while any document is still being processed.
  React.useEffect(() => {
    if (!docs?.some((d) => isActive(d.status))) return;
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, [docs, load]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      toast(`Unsupported type. Allowed: ${ACCEPTED.join(", ")}`, "error");
      return;
    }
    if (file.size > MAX_BYTES) {
      toast("File is larger than 10 MB.", "error");
      return;
    }
    setUploading(true);
    try {
      await api.uploadDocument(file);
      toast(`Uploading “${file.name}” — indexing started.`, "success");
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast("Configure an embedding provider in Settings first.", "error");
      } else {
        toast(err instanceof ApiError ? err.message : "Upload failed.", "error");
      }
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove(doc: Document) {
    if (!confirm(`Delete “${doc.filename}”? This removes its chunks and vectors.`)) return;
    try {
      await api.deleteDocument(doc.id);
      toast("Document deleted.", "success");
      setDocs((prev) => prev?.filter((d) => d.id !== doc.id) ?? null);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Delete failed.", "error");
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Documents"
        description="Upload text files to index. Supported: .txt, .md (max 10 MB)."
      />

      {/* Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "mt-8 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors",
          dragging ? "border-primary bg-accent" : "border-border hover:border-input hover:bg-muted",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <UploadCloud className="h-6 w-6" />
        </div>
        <p className="text-sm font-medium text-foreground">
          {uploading ? "Uploading…" : "Drag a file here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">.txt or .md · up to 10 MB</p>
      </div>

      {/* List */}
      <div className="mt-8">
        {docs === null ? (
          <CenteredSpinner label="Loading documents…" />
        ) : docs.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-6 w-6" />}
            title="No documents yet"
            description="Upload your first file above. Once it's ready, ask questions about it in Chat."
          />
        ) : (
          <div className="space-y-2">
            {docs.map((doc) => (
              <Card key={doc.id} className="flex items-center gap-4 p-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <FileText className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{doc.filename}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {doc.source_type}
                    {doc.status === "failed" && doc.error_msg ? ` · ${doc.error_msg}` : ""}
                  </p>
                </div>
                <DocStatusBadge status={doc.status} />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => remove(doc)}
                  aria-label={`Delete ${doc.filename}`}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </Card>
            ))}
          </div>
        )}
      </div>

      <p className="mt-6 text-center text-xs text-muted-foreground">
        Need to change models?{" "}
        <Link href="/settings" className="text-primary hover:underline">
          Provider settings
        </Link>
      </p>
    </PageContainer>
  );
}
