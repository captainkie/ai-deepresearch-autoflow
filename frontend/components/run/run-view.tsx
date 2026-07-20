"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, WifiOff, RotateCcw, Plus } from "lucide-react";
import { toast } from "sonner";

import { useResearchStream } from "@/lib/useResearchStream";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { RunHeader } from "@/components/run/run-header";
import { ProgressTimeline } from "@/components/run/progress-timeline";
import { PlanReviewCard } from "@/components/run/plan-review-card";
import { ReportView } from "@/components/run/report-view";
import { ThinkingState } from "@/components/run/thinking-state";

export function RunView({ runId }: { runId: string }) {
  const s = useResearchStream(runId);
  const [canceling, setCanceling] = React.useState(false);

  async function handleCancel() {
    setCanceling(true);
    try {
      await s.cancel();
      toast("Cancelling research…");
    } catch (err) {
      toast.error("Couldn't cancel", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setCanceling(false);
    }
  }

  async function handleApprove(sections?: Parameters<typeof s.approvePlan>[0]) {
    try {
      await s.approvePlan(sections);
      toast.success("Plan approved — research is starting");
    } catch (err) {
      toast.error("Couldn't submit the plan", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }

  const hasReport = s.report.trim().length > 0;
  const streaming = hasReport && !s.reportFinal && s.status !== "done";
  const streamDropped =
    s.connection === "error" &&
    s.status !== "done" &&
    s.status !== "error" &&
    !s.awaitingPlan;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <RunHeader
        query={s.query}
        title={s.title}
        template={s.template}
        status={s.status}
        createdAt={s.createdAt}
        sourceCount={s.sourceCount ?? (s.allSources.length || undefined)}
        canceling={canceling}
        onCancel={handleCancel}
      />

      {streamDropped && (
        <Alert className="mt-5">
          <WifiOff />
          <AlertTitle>Live updates paused</AlertTitle>
          <AlertDescription>
            <span>
              We lost the connection to the research stream
              {s.connectionError ? ` (${s.connectionError})` : ""}. Your run keeps
              going on the server — reconnect to see the latest.
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={s.retry}
              className="mt-1 w-fit gap-1.5"
            >
              <RotateCcw className="size-3.5" data-icon="inline-start" />
              Reconnect
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-6 grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Progress rail (desktop) */}
        <aside className="thin-scroll hidden lg:sticky lg:top-20 lg:block lg:max-h-[calc(100vh-6rem)] lg:self-start lg:overflow-y-auto lg:pr-1">
          <div className="mb-4 flex items-center gap-2">
            <span className="eyebrow">Progress</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <ProgressTimeline sections={s.sections} />
        </aside>

        {/* Main column */}
        <div className="min-w-0">
          {/* Progress (mobile, collapsible) */}
          {s.sections.length > 0 && (
            <details className="group mb-5 rounded-xl border border-border/70 bg-card/50 lg:hidden">
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
                <span className="eyebrow">
                  Progress · {s.sections.length} sections
                </span>
                <Plus className="size-4 text-muted-foreground transition-transform group-open:rotate-45" />
              </summary>
              <div className="px-4 pb-4">
                <ProgressTimeline sections={s.sections} />
              </div>
            </details>
          )}

          <MainContent
            status={s.status}
            statusMessage={s.statusMessage}
            error={s.error}
            awaitingPlan={s.awaitingPlan}
            brief={s.brief}
            planSections={s.planSections}
            approving={s.approving}
            onApprove={handleApprove}
            hasReport={hasReport}
            report={s.report}
            reportTitle={s.title}
            query={s.query}
            streaming={streaming}
          />
        </div>
      </div>
    </div>
  );
}

function MainContent({
  status,
  statusMessage,
  error,
  awaitingPlan,
  brief,
  planSections,
  approving,
  onApprove,
  hasReport,
  report,
  streaming,
  reportTitle,
  query,
}: {
  status: string;
  statusMessage: string;
  error?: string;
  awaitingPlan: boolean;
  brief?: string;
  planSections: import("@/lib/types").PlanSection[];
  approving: boolean;
  onApprove: (s?: import("@/lib/types").PlanSection[]) => void;
  hasReport: boolean;
  report: string;
  streaming: boolean;
  reportTitle?: string;
  query?: string;
}) {
  if (status === "error" && error) {
    return (
      <div className="space-y-5">
        {hasReport && (
          <ReportView markdown={report} title={reportTitle} query={query} />
        )}
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Research ran into a problem</AlertTitle>
          <AlertDescription>
            <span>{error}</span>
            <Button asChild variant="outline" size="sm" className="mt-1 w-fit gap-1.5">
              <Link href="/">
                <Plus className="size-3.5" data-icon="inline-start" />
                Start a new run
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (awaitingPlan) {
    return (
      <div className="space-y-5">
        <PlanReviewCard
          brief={brief}
          sections={planSections}
          approving={approving}
          onApprove={onApprove}
        />
      </div>
    );
  }

  if (hasReport) {
    return (
      <ReportView
        markdown={report}
        title={reportTitle}
        query={query}
        streaming={streaming}
      />
    );
  }

  return <ThinkingState status={status} message={statusMessage} />;
}
