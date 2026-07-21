"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UsersPanel } from "@/components/admin/users-panel";
import { CredentialsPanel } from "@/components/admin/credentials-panel";
import { AuditPanel } from "@/components/admin/audit-panel";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = !!user && (user.role === "admin" || user.role === "superadmin");

  React.useEffect(() => {
    if (user && !isAdmin) router.replace("/");
  }, [user, isAdmin, router]);

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center text-muted-foreground">
        <ShieldAlert className="mx-auto mb-3 size-8" />
        <p>Admins only.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold tracking-tight">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Manage members, provider keys, and review the audit trail.
        </p>
      </header>
      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="credentials">Provider keys</TabsTrigger>
          <TabsTrigger value="audit">Audit log</TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="mt-5">
          <UsersPanel />
        </TabsContent>
        <TabsContent value="credentials" className="mt-5">
          <CredentialsPanel />
        </TabsContent>
        <TabsContent value="audit" className="mt-5">
          <AuditPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
