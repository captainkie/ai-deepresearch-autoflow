"use client";

import * as React from "react";
import { Copy, Check, Download, List } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ReportMarkdown, extractToc } from "@/components/markdown";
import { slugify } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ReportView({
  markdown,
  title,
  query,
  streaming = false,
}: {
  markdown: string;
  title?: string;
  query?: string;
  streaming?: boolean;
}) {
  const [copied, setCopied] = React.useState(false);
  const toc = React.useMemo(() => extractToc(markdown), [markdown]);
  const [activeId, setActiveId] = React.useState<string>("");
  const articleRef = React.useRef<HTMLDivElement>(null);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      toast.success("Report copied to clipboard");
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error("Couldn't copy — try selecting the text manually");
    }
  }

  function handleDownload() {
    const name = slugify(title || query || "autoflow-report") || "report";
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast.success("Report downloaded");
  }

  // Scroll-spy over rendered headings.
  React.useEffect(() => {
    if (!toc.length || streaming) return;
    const el = articleRef.current;
    if (!el) return;
    const headings = toc
      .map((t) => el.querySelector<HTMLElement>(`#${CSS.escape(t.id)}`))
      .filter((h): h is HTMLElement => !!h);
    if (!headings.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 },
    );
    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [toc, streaming]);

  return (
    <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_14rem] xl:gap-10">
      <article className="min-w-0">
        <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <span className="eyebrow">Report</span>
            {streaming && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-signal/15 px-2 py-0.5 text-[0.7rem] font-medium text-[color-mix(in_oklch,var(--signal),var(--foreground)_45%)]">
                <span className="size-1.5 rounded-full bg-signal pulse-dot" />
                Writing
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-1.5"
            >
              {copied ? (
                <Check className="size-3.5" data-icon="inline-start" />
              ) : (
                <Copy className="size-3.5" data-icon="inline-start" />
              )}
              {copied ? "Copied" : "Copy"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              className="gap-1.5"
              disabled={streaming}
            >
              <Download className="size-3.5" data-icon="inline-start" />
              <span className="hidden sm:inline">Download</span>
              <span className="sm:hidden">.md</span>
            </Button>
          </div>
        </div>

        <div ref={articleRef}>
          <ReportMarkdown content={markdown} />
          {streaming && (
            <span className="ml-0.5 inline-block h-5 w-1.5 translate-y-1 animate-pulse rounded-full bg-primary align-middle" />
          )}
        </div>
      </article>

      {toc.length > 1 && (
        <aside className="hidden xl:block">
          <div className="sticky top-24">
            <p className="eyebrow mb-3 flex items-center gap-1.5">
              <List className="size-3" /> Contents
            </p>
            <nav className="flex flex-col gap-0.5 border-l border-border">
              {toc.map((item) => (
                <a
                  key={`${item.id}-${item.level}`}
                  href={`#${item.id}`}
                  className={cn(
                    "-ml-px border-l-2 py-1 text-sm leading-snug transition-colors",
                    item.level === 3 ? "pl-5 text-[0.8rem]" : "pl-3",
                    activeId === item.id
                      ? "border-primary font-medium text-primary"
                      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                  )}
                >
                  {item.text}
                </a>
              ))}
            </nav>
          </div>
        </aside>
      )}
    </div>
  );
}
