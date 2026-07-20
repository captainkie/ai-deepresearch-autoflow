import { Check, X } from "lucide-react";

import type { RunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS: { key: RunStatus; label: string }[] = [
  { key: "planning", label: "Plan" },
  { key: "awaiting_plan", label: "Review" },
  { key: "researching", label: "Research" },
  { key: "writing", label: "Write" },
  { key: "done", label: "Report" },
];

const ORDER: Record<string, number> = {
  queued: 0,
  planning: 1,
  awaiting_plan: 2,
  researching: 3,
  writing: 4,
  done: 5,
  error: 5,
};

export function StageStepper({ status }: { status: RunStatus }) {
  const current = ORDER[status] ?? 0;
  const isError = status === "error";

  return (
    <ol className="flex items-center gap-1.5">
      {STEPS.map((step, i) => {
        const stepIndex = i + 1;
        const done = current > stepIndex || status === "done";
        const active = current === stepIndex && !isError;
        const errored = isError && current === stepIndex;

        return (
          <li key={step.key} className="flex items-center gap-1.5">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium transition-colors",
                active && "bg-primary/10 text-primary",
                done && "text-primary",
                errored && "bg-destructive/10 text-destructive",
                !active && !done && !errored && "text-muted-foreground/60",
              )}
            >
              <span
                className={cn(
                  "flex size-4 items-center justify-center rounded-full text-[0.6rem] font-semibold ring-1 transition-all",
                  active && "bg-primary text-primary-foreground ring-primary",
                  done && "bg-primary/15 text-primary ring-primary/30",
                  errored && "bg-destructive text-white ring-destructive",
                  !active &&
                    !done &&
                    !errored &&
                    "text-muted-foreground/60 ring-border",
                )}
              >
                {done ? (
                  <Check className="size-2.5" strokeWidth={3} />
                ) : errored ? (
                  <X className="size-2.5" strokeWidth={3} />
                ) : (
                  stepIndex
                )}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </span>
            {i < STEPS.length - 1 && (
              <span
                className={cn(
                  "h-px w-3 sm:w-4",
                  current > stepIndex ? "bg-primary/40" : "bg-border",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
