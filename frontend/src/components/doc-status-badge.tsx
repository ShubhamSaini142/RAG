import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/types";

export function DocStatusBadge({ status }: { status: DocumentStatus }) {
  switch (status) {
    case "ready":
      return (
        <Badge tone="success">
          <CheckCircle2 className="h-3.5 w-3.5" /> Ready
        </Badge>
      );
    case "processing":
      return (
        <Badge tone="primary">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing
        </Badge>
      );
    case "queued":
      return (
        <Badge tone="warning">
          <Clock className="h-3.5 w-3.5" /> Queued
        </Badge>
      );
    case "failed":
      return (
        <Badge tone="destructive">
          <XCircle className="h-3.5 w-3.5" /> Failed
        </Badge>
      );
  }
}
