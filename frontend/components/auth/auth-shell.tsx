import { BrandLockup } from "@/components/brand";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] w-full max-w-md flex-col justify-center px-4 py-10">
      <div className="mb-6 flex justify-center">
        <BrandLockup />
      </div>
      <div className="rounded-2xl border border-border/70 bg-card p-6 shadow-[var(--shadow-soft)] sm:p-7">
        <div className="mb-5 space-y-1.5 text-center">
          <h1 className="font-display text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        {children}
      </div>
      {footer ? (
        <div className="mt-4 text-center text-sm text-muted-foreground">{footer}</div>
      ) : null}
    </div>
  );
}
