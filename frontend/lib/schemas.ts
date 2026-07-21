/**
 * Zod validation schemas — the single source of truth for form input on the
 * client. Rules mirror the backend Pydantic constraints (EmailStr, password
 * min 8, non-empty trimmed name) so the browser catches bad input before a
 * round-trip and the two layers never disagree.
 */
import { z } from "zod";

const email = z.email({ message: "Enter a valid email address." }).max(254);
const password = z
  .string()
  .min(8, "Password must be at least 8 characters.")
  .max(128, "Password is too long.");
const name = z
  .string()
  .trim()
  .min(1, "Name is required.")
  .max(120, "Name is too long.");

// --- Auth ---------------------------------------------------------------
export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Password is required."),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({ name, email, password });
export type RegisterValues = z.infer<typeof registerSchema>;

// First-run superadmin — same shape as register.
export const setupSchema = z.object({ name, email, password });
export type SetupValues = z.infer<typeof setupSchema>;

// --- Research composer --------------------------------------------------
export const composerSchema = z.object({
  query: z
    .string()
    .trim()
    .min(1, "Tell me what you want to research.")
    .max(2000, "That's a bit long — try to focus the question."),
});
export type ComposerValues = z.infer<typeof composerSchema>;

// --- Admin: provider credential ----------------------------------------
export const credentialSchema = z.object({
  provider: z.string().trim().min(1, "Choose a provider."),
  // Optional — falls back to the provider name when left blank.
  label: z.string().trim().max(120, "Label is too long.").optional(),
  secret: z.string().min(1, "Paste the API key."),
  expiresOn: z.string().optional(),
});
export type CredentialValues = z.infer<typeof credentialSchema>;
