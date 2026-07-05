import { Boxes } from "lucide-react";
import { cn } from "@/lib/utils";

export function Brand({
  className,
  showText = true,
}: {
  className?: string;
  showText?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <Boxes className="h-5 w-5" />
      </span>
      {showText && (
        <span className="text-lg font-semibold tracking-tight text-foreground">
          RAG<span className="text-primary"> KB</span>
        </span>
      )}
    </div>
  );
}
