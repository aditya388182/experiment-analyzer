import type { ReactNode } from "react";

import { ApiError } from "../api/client";

export function Card({ title, children, className = "" }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-stone-200 bg-white p-5 shadow-sm ${className}`}>
      {title ? <h2 className="mb-3 text-base font-semibold text-stone-800">{title}</h2> : null}
      {children}
    </section>
  );
}

/** Shows the server's error message (and code), so every API error reaches the user. */
export function ErrorMessage({ error, title = "Something went wrong" }: { error: unknown; title?: string }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "Unexpected error.";
  const code = error instanceof ApiError ? error.code : null;
  return (
    <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <p className="font-semibold">{title}</p>
      <p>
        {message}
        {code ? <span className="ml-2 font-mono text-xs text-red-700">({code})</span> : null}
      </p>
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  const styles =
    variant === "primary"
      ? "bg-teal-700 text-white hover:bg-teal-800 disabled:bg-stone-400"
      : "border border-stone-300 bg-white text-stone-800 hover:bg-stone-100 disabled:text-stone-400";
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums text-stone-900">{value}</dd>
      {hint ? <dd className="text-xs text-stone-500">{hint}</dd> : null}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-stone-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-stone-300 border-t-teal-700" aria-hidden="true" />
      {label}
    </span>
  );
}

export const inputClass =
  "mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600 aria-[invalid=true]:border-red-500";

export function FieldError({ id, message }: { id: string; message?: string | undefined }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1 text-xs text-red-700">
      {message}
    </p>
  );
}
