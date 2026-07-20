"use client";

import * as React from "react";
import { Globe, ArrowUpRight } from "lucide-react";

import type { Source } from "@/lib/types";
import { domainFromUrl, faviconUrl } from "@/lib/format";
import { cn } from "@/lib/utils";

export function SourceItem({
  source,
  className,
  compact = false,
}: {
  source: Source;
  className?: string;
  compact?: boolean;
}) {
  const [imgOk, setImgOk] = React.useState(true);
  const domain = domainFromUrl(source.url);
  const favicon = faviconUrl(source.url);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "group flex items-start gap-2.5 rounded-lg border border-border/60 bg-card/60 p-2.5 transition-all hover:border-primary/40 hover:bg-accent/40",
        className,
      )}
    >
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted ring-1 ring-border/60">
        {favicon && imgOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={favicon}
            alt=""
            width={16}
            height={16}
            className="size-4"
            onError={() => setImgOk(false)}
            loading="lazy"
          />
        ) : (
          <Globe className="size-3.5 text-muted-foreground" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1">
          <span
            className={cn(
              "truncate font-medium text-foreground group-hover:text-primary",
              compact ? "text-xs" : "text-[0.82rem]",
            )}
          >
            {source.title || domain}
          </span>
          <ArrowUpRight className="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
          <span className="rounded bg-muted px-1 font-mono tabular-nums">
            {source.id}
          </span>
          <span className="truncate">{domain}</span>
        </span>
        {!compact && source.snippet && (
          <span className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {source.snippet}
          </span>
        )}
      </span>
    </a>
  );
}
