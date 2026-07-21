"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Coffee, Heart } from "lucide-react";

import { BrandMark } from "@/components/brand";
import { cn } from "@/lib/utils";

// Auth screens are short and self-contained; the tall top margin that gives
// content pages breathing room turns into viewport overflow (a scrollbar) there,
// so collapse it — `main` (flex-1) already pins the footer to the bottom.
const MINIMAL_ROUTES = new Set(["/login", "/register", "/setup"]);

export function SiteFooter() {
  const pathname = usePathname();
  const minimal = MINIMAL_ROUTES.has(pathname);
  return (
    <footer className={cn("border-t border-border/70", minimal ? "mt-0" : "mt-16")}>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-6" />
            <span className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">AutoFlow Research</span>
              {" — "}research desk for marketing teams.
            </span>
          </div>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link href="/about" className="transition-colors hover:text-foreground">
              About &amp; credits
            </Link>
            <a
              href="https://github.com/sponsors/captainkie"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
            >
              <Heart className="size-3.5" /> Sponsor
            </a>
            <a
              href="https://buymeacoffee.com/captainkiez"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
            >
              <Coffee className="size-3.5" /> Coffee
            </a>
          </nav>
        </div>
        <div className="flex flex-col gap-1 border-t border-border/50 pt-4 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            Built by Narenrit Hadsadintorn &amp; Claude (Anthropic) ·{" "}
            <span className="font-medium text-foreground">MIT</span> licensed
          </p>
          <p>Reports are AI-generated. Verify critical facts against the linked sources.</p>
        </div>
      </div>
    </footer>
  );
}
