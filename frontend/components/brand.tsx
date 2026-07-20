import { cn } from "@/lib/utils";

/**
 * AutoFlow brand mark — an abstract "flow" glyph: a research path threading
 * through nodes, synthesised into a single line. Uses currentColor for the
 * stroke so it inherits the tile's foreground.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-[0.6rem] bg-primary text-primary-foreground shadow-[0_1px_0_oklch(1_0_0/0.25)_inset]",
        className,
      )}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className="size-[62%]"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 17c3 0 3-10 8-10s5 10 8 10" opacity={0.9} />
        <circle cx="4" cy="17" r="1.6" fill="currentColor" stroke="none" />
        <circle cx="20" cy="17" r="1.6" fill="currentColor" stroke="none" />
        <circle cx="12" cy="7" r="1.9" fill="currentColor" stroke="none" />
      </svg>
    </span>
  );
}

export function BrandLockup({
  className,
  markClassName,
}: {
  className?: string;
  markClassName?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark className={cn("size-8", markClassName)} />
      <span className="flex flex-col leading-none">
        <span className="font-display text-[1.05rem] font-semibold tracking-tight text-foreground">
          AutoFlow
        </span>
        <span className="eyebrow mt-0.5 text-[0.6rem] tracking-[0.22em]">
          Research
        </span>
      </span>
    </span>
  );
}
