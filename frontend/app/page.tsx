import { ListChecks, Search, FileText } from "lucide-react";

import { ResearchComposer } from "@/components/home/research-composer";

const STEPS = [
  {
    icon: ListChecks,
    title: "It plans",
    body: "A research brief and a set of focused sections — yours to review and edit.",
  },
  {
    icon: Search,
    title: "It researches",
    body: "Live web searches across every section, gathering and weighing real sources.",
  },
  {
    icon: FileText,
    title: "It writes",
    body: "A structured, cited report you can read, copy, or download as Markdown.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 pt-14 pb-8 sm:px-6 sm:pt-20">
      <section className="mb-9 text-center">
        <span className="eyebrow inline-flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary" />
          Autonomous research, human-guided
        </span>
        <h1 className="mt-4 font-display text-4xl leading-[1.05] font-semibold tracking-[-0.02em] text-balance sm:text-5xl">
          Research any brand or market,{" "}
          <span className="italic text-primary">end to end.</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-[1.05rem] leading-relaxed text-muted-foreground text-balance">
          Ask a question. AutoFlow plans the investigation, searches the open web,
          and writes you a cited report — the kind of competitor and market
          research your team can act on.
        </p>
      </section>

      <ResearchComposer />

      <section className="mt-16">
        <div className="mb-5 flex items-center gap-3">
          <span className="eyebrow">How it works</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <li
                key={step.title}
                className="relative rounded-xl border border-border/70 bg-card/50 p-4"
              >
                <div className="mb-3 flex items-center gap-2.5">
                  <span className="inline-flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-4" />
                  </span>
                  <span className="font-display text-2xl font-semibold tabular-nums text-muted-foreground/40">
                    0{i + 1}
                  </span>
                </div>
                <h3 className="font-display text-base font-semibold tracking-tight">
                  {step.title}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}
