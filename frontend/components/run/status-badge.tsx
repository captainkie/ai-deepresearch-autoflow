import type { RunStatus } from "@/lib/types";
import { statusMeta, type StatusTone } from "@/lib/format";
import { cn } from "@/lib/utils";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  pending: "bg-muted text-foreground/80 ring-1 ring-border",
  active: "bg-signal/15 text-[color-mix(in_oklch,var(--signal),var(--foreground)_45%)]",
  success: "bg-primary/12 text-primary",
  danger: "bg-destructive/12 text-destructive",
};

const DOT_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-muted-foreground",
  pending: "bg-muted-foreground",
  active: "bg-signal pulse-dot",
  success: "bg-primary",
  danger: "bg-destructive",
};

export function StatusBadge({
  status,
  className,
  showDot = true,
}: {
  status: RunStatus;
  className?: string;
  showDot?: boolean;
}) {
  const meta = statusMeta(status);
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium",
        TONE_CLASSES[meta.tone],
        className,
      )}
    >
      {showDot && (
        <span className={cn("size-1.5 rounded-full", DOT_CLASSES[meta.tone])} />
      )}
      {meta.label}
    </span>
  );
}
