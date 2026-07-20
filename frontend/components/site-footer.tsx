import { BrandMark } from "@/components/brand";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-border/70">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-2.5">
          <BrandMark className="size-6" />
          <span className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">AutoFlow Research</span>
            {" — "}research desk for marketing teams.
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Reports are AI-generated. Verify critical facts against the linked sources.
        </p>
      </div>
    </footer>
  );
}
