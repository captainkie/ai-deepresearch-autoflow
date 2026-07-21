"use client";

import * as React from "react";
import { toast } from "sonner";

import { listAudit } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";
import { PanelLoading, Td, Th } from "./primitives";

export function AuditPanel() {
  const [rows, setRows] = React.useState<AuditEntry[] | null>(null);

  const load = React.useCallback(async () => {
    try {
      setRows(await listAudit(150));
    } catch (err) {
      toast.error("Couldn't load audit log", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }, []);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  if (!rows) return <PanelLoading />;

  return (
    <div className="overflow-x-auto rounded-xl border border-border/70">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <Th>Action</Th>
            <Th>Target</Th>
            <Th>Details</Th>
            <Th className="text-right">When</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                No audit entries yet.
              </td>
            </tr>
          ) : null}
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-muted/20">
              <Td>
                <code className="text-xs">{r.action}</code>
              </Td>
              <Td className="text-xs text-muted-foreground">
                {r.target_id ? `${r.target_type ?? ""}:${r.target_id.slice(0, 8)}` : "—"}
              </Td>
              <Td className="max-w-[16rem] truncate text-xs text-muted-foreground">
                {r.meta_json ?? "—"}
              </Td>
              <Td className="text-right text-xs text-muted-foreground">
                {new Date(r.created_at).toLocaleString()}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
