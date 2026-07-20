import { SettingsForm } from "@/components/settings/settings-form";

export const metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7 border-b border-border/70 pb-5">
        <span className="eyebrow">Configuration</span>
        <h1 className="mt-1.5 font-display text-3xl font-semibold tracking-tight">
          Settings
        </h1>
        <p className="mt-1.5 max-w-lg text-sm text-muted-foreground">
          Choose the models and search provider that power your research, and
          decide whether runs pause for plan approval.
        </p>
      </div>
      <SettingsForm />
    </div>
  );
}
