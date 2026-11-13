import type { MetricType } from "../api/types";

export const pct = (x: number, digits = 1): string => `${(x * 100).toFixed(digits)}%`;

/** Effect in display units: percentage points for binary metrics, metric units otherwise. */
export function effect(x: number, type: MetricType): string {
  if (type === "binary") return `${(x * 100).toFixed(2)} pts`;
  return x.toFixed(Math.abs(x) >= 100 ? 1 : 3); // one precision per table, so 0.485 to 1.055 lines up
}

export function mean(x: number, type: MetricType): string {
  return type === "binary" ? pct(x, 2) : x.toFixed(3);
}

export function pValue(p: number): string {
  if (p >= 0.001) return p.toFixed(3);
  if (p === 0) return "< 1e-300";
  return p.toExponential(1);
}

export const int = (n: number): string => n.toLocaleString("en-US");

export const shortSha = (s: string | null, n = 12): string => (s ? s.slice(0, n) : "—");

export function when(iso: string): string {
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}
