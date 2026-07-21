/**
 * Published credentials for the hosted demo's shared **admin**-role account.
 *
 * These are intentionally public: the demo forces mock providers, disables
 * credential entry / provider switching, rate-limits requests, and periodically
 * resets its ephemeral database — so a shared admin login can't run up cost or
 * cause lasting harm. It lets visitors explore the admin panel (users, audit, the
 * credentials screen) without exposing the operator's private superadmin.
 *
 * Keep in sync with the backend seed (`AUTOFLOW_DEMO_PUBLIC_ADMIN_*`, see render.yaml).
 */
export const DEMO_ADMIN = {
  email: "demo-admin@autoflow-research.fosivo.com",
  password: "autoflow-demo-admin",
} as const;
