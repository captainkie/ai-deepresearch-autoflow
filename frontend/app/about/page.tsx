"use client";

import * as React from "react";
import { Coffee, ExternalLink, Heart, Star } from "lucide-react";

import { getAbout } from "@/lib/api";
import type { About } from "@/lib/types";
import { BrandLockup } from "@/components/brand";
import { PanelLoading } from "@/components/admin/primitives";

const REPO = "https://github.com/captainkie/ai-deepresearch-autoflow";

export default function AboutPage() {
  const [about, setAbout] = React.useState<About | null>(null);
  const [failed, setFailed] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      setAbout(await getAbout());
    } catch {
      setFailed(true);
    }
  }, []);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-12 sm:px-6">
      <div className="mb-10 flex flex-col items-center gap-2 text-center">
        <BrandLockup />
        {about ? (
          <a
            href={about.org.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-foreground transition-colors hover:text-primary"
          >
            A product of {about.org.name}
          </a>
        ) : null}
        <p className="text-sm text-muted-foreground">
          {about ? `v${about.version} · ${about.license} licensed` : "Deep research your team can trust"}
        </p>
      </div>

      {!about && !failed ? <PanelLoading /> : null}
      {failed ? (
        <p className="text-center text-sm text-muted-foreground">Couldn&apos;t load credits.</p>
      ) : null}

      {about ? (
        <div className="space-y-10">
          <section>
            <h2 className="eyebrow mb-3">Built by</h2>
            <ul className="space-y-2">
              {about.authors.map((a) => (
                <li
                  key={a.name}
                  className="flex items-center justify-between rounded-lg border border-border/70 bg-card/40 px-3.5 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium">{a.name}</p>
                    {a.role ? <p className="text-xs text-muted-foreground">{a.role}</p> : null}
                  </div>
                  {a.handle ? (
                    <span className="text-xs text-muted-foreground">@{a.handle}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="eyebrow mb-3">Acknowledgements</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              Original code, inspired by the patterns of these open-source projects:
            </p>
            <ul className="space-y-2">
              {about.acknowledgements.map((ack) => (
                <li
                  key={ack.name}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/40 px-3.5 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{ack.name}</p>
                    {ack.license ? (
                      <p className="text-xs text-muted-foreground">{ack.license}</p>
                    ) : null}
                  </div>
                  {ack.url ? (
                    <a
                      href={ack.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      Visit <ExternalLink className="size-3" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="eyebrow mb-3">Support this project</h2>
            <div className="flex flex-wrap gap-2.5">
              <a
                href={REPO}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-card px-3.5 py-2 text-sm font-medium transition-colors hover:border-primary/40"
              >
                <Star className="size-4 text-amber-500" /> Star on GitHub
              </a>
              <a
                href="https://github.com/sponsors/captainkie"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-card px-3.5 py-2 text-sm font-medium transition-colors hover:border-primary/40"
              >
                <Heart className="size-4 text-pink-500" /> Sponsor
              </a>
              <a
                href="https://buymeacoffee.com/captainkiez"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-card px-3.5 py-2 text-sm font-medium transition-colors hover:border-primary/40"
              >
                <Coffee className="size-4 text-yellow-600" /> Buy me a coffee
              </a>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
