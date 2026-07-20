"use client";

import * as React from "react";
import Link from "next/link";
import { RefreshCw, Plus, Compass, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty";
import { RunCard } from "@/components/history/run-card";
import { listRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

type LoadState = "loading" | "ready" | "error";

export default function HistoryPage() {
  const [runs, setRuns] = React.useState<RunSummary[]>([]);
  const [state, setState] = React.useState<LoadState>("loading");
  const [refreshing, setRefreshing] = React.useState(false);

  const load = React.useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setState("loading");
    try {
      const data = await listRuns();
      setRuns(data);
      setState("ready");
    } catch {
      setState("error");
    } finally {
      setRefreshing(false);
    }
  }, []);

  // Initial load — setState happens in the async callback (initial state is
  // already "loading"), avoiding a synchronous setState in the effect body.
  React.useEffect(() => {
    let active = true;
    listRuns()
      .then((data) => {
        if (active) {
          setRuns(data);
          setState("ready");
        }
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/70 pb-5">
        <div>
          <span className="eyebrow">Archive</span>
          <h1 className="mt-1.5 font-display text-3xl font-semibold tracking-tight">
            Research history
          </h1>
          <p className="mt-1.5 max-w-lg text-sm text-muted-foreground">
            Every run your team has started, newest first. Open one to revisit its
            plan, sources, and report.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => load(true)}
            disabled={refreshing || state === "loading"}
            className="gap-1.5"
          >
            <RefreshCw
              className={`size-3.5 ${refreshing ? "animate-spin" : ""}`}
              data-icon="inline-start"
            />
            Refresh
          </Button>
          <Button asChild size="sm" className="gap-1.5">
            <Link href="/">
              <Plus className="size-4" data-icon="inline-start" />
              New research
            </Link>
          </Button>
        </div>
      </div>

      <div className="mt-6">
        {state === "loading" && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
              >
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="mt-2 h-4 w-32" />
              </div>
            ))}
          </div>
        )}

        {state === "error" && (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <WifiOff />
              </EmptyMedia>
              <EmptyTitle>Couldn&apos;t reach the research service</EmptyTitle>
              <EmptyDescription>
                The backend looks offline. Start it, then refresh to see your run
                history.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" size="sm" onClick={() => load()} className="gap-1.5">
                <RefreshCw className="size-3.5" data-icon="inline-start" />
                Try again
              </Button>
            </EmptyContent>
          </Empty>
        )}

        {state === "ready" && runs.length === 0 && (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Compass />
              </EmptyMedia>
              <EmptyTitle>No research yet</EmptyTitle>
              <EmptyDescription>
                Your completed and in-progress runs will collect here. Kick off
                your first investigation to get started.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button asChild size="sm" className="gap-1.5">
                <Link href="/">
                  <Plus className="size-4" data-icon="inline-start" />
                  Start research
                </Link>
              </Button>
            </EmptyContent>
          </Empty>
        )}

        {state === "ready" && runs.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {runs.map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
