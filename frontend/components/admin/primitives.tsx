import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export function Th({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return <th className={cn("px-3 py-2 text-left font-medium", className)}>{children}</th>;
}

export function Td({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return <td className={cn("px-3 py-2.5 align-middle", className)}>{children}</td>;
}

export function StatusPill({ ok, labels }: { ok: boolean; labels: [string, string] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        ok
          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          : "bg-muted text-muted-foreground",
      )}
    >
      <span className={cn("size-1.5 rounded-full", ok ? "bg-emerald-500" : "bg-muted-foreground/50")} />
      {ok ? labels[0] : labels[1]}
    </span>
  );
}

export function PanelLoading() {
  return (
    <div className="flex items-center justify-center py-16 text-muted-foreground" aria-busy="true">
      <Loader2 className="size-5 animate-spin" />
    </div>
  );
}
