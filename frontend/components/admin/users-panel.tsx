"use client";

import * as React from "react";
import { toast } from "sonner";

import { listUsers, updateUser } from "@/lib/api";
import type { Role, User } from "@/lib/types";
import { useAuth } from "@/components/auth-provider";
import { PanelLoading, StatusPill, Td, Th } from "./primitives";

const ROLES: Role[] = ["superadmin", "admin", "member", "viewer"];

export function UsersPanel() {
  const { user: me } = useAuth();
  const [users, setUsers] = React.useState<User[] | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      setUsers(await listUsers());
    } catch (err) {
      toast.error("Couldn't load users", {
        description: err instanceof Error ? err.message : undefined,
      });
    }
  }, []);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function patch(updated: User) {
    setUsers((cur) => cur?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
  }

  async function changeRole(u: User, role: Role) {
    setBusy(u.id);
    try {
      patch(await updateUser(u.id, { role }));
      toast.success(`Role updated to ${role}`);
    } catch (err) {
      toast.error("Couldn't change role", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setBusy(null);
    }
  }

  async function toggleDisabled(u: User) {
    setBusy(u.id);
    try {
      patch(await updateUser(u.id, { disabled: !u.disabled }));
    } catch (err) {
      toast.error("Couldn't update user", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setBusy(null);
    }
  }

  if (!users) return <PanelLoading />;

  return (
    <div className="overflow-x-auto rounded-xl border border-border/70">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <Th>User</Th>
            <Th>Role</Th>
            <Th>Status</Th>
            <Th className="text-right">Actions</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-muted/20">
              <Td>
                <div className="font-medium">
                  {u.name}
                  {u.id === me?.id ? (
                    <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>
                  ) : null}
                </div>
                <div className="text-xs text-muted-foreground">{u.email}</div>
              </Td>
              <Td>
                <select
                  value={u.role}
                  disabled={busy === u.id}
                  onChange={(e) => changeRole(u, e.target.value as Role)}
                  className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm disabled:opacity-50"
                  aria-label={`Role for ${u.name}`}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </Td>
              <Td>
                <StatusPill ok={!u.disabled} labels={["Active", "Disabled"]} />
              </Td>
              <Td className="text-right">
                <button
                  type="button"
                  onClick={() => toggleDisabled(u)}
                  disabled={busy === u.id || u.id === me?.id}
                  className="text-xs font-medium text-primary hover:underline disabled:opacity-40"
                >
                  {u.disabled ? "Enable" : "Disable"}
                </button>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
