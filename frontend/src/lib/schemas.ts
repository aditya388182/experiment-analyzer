import { z } from "zod";

import type { Mapping } from "../api/types";

/** Parse "0.5, 0.5" into numbers; returns null for an empty string. */
export function parseSplit(raw: string): number[] | null {
  const t = raw.trim();
  if (!t) return null;
  return t.split(/[,\s]+/).filter(Boolean).map(Number);
}

export const mappingSchema = z
  .object({
    variant_col: z.string().min(1, "Pick the column that says which variant each row saw."),
    control_label: z.string().trim().min(1, "Enter the control group's label."),
    metric_col: z.string().min(1, "Pick the outcome (metric) column."),
    metric_type: z.enum(["binary", "continuous"]),
    pre_period_col: z.string(),
    planned_split: z.string(),
    alpha: z.coerce
      .number({ error: "Alpha must be a number." })
      .gt(0, "Alpha must be greater than 0.")
      .lte(0.2, "Alpha must be at most 0.2."),
  })
  .superRefine((v, ctx) => {
    if (v.metric_col && v.metric_col === v.variant_col) {
      ctx.addIssue({ code: "custom", path: ["metric_col"], message: "The metric column must differ from the variant column." });
    }
    if (v.pre_period_col && (v.pre_period_col === v.metric_col || v.pre_period_col === v.variant_col)) {
      ctx.addIssue({ code: "custom", path: ["pre_period_col"], message: "The pre-period column must be a different column." });
    }
    const split = parseSplit(v.planned_split);
    if (split) {
      if (split.some((s) => !Number.isFinite(s) || s <= 0)) {
        ctx.addIssue({ code: "custom", path: ["planned_split"], message: "Each share must be a positive number." });
      } else if (split.length < 2 || split.length > 10) {
        ctx.addIssue({ code: "custom", path: ["planned_split"], message: "Give one share per arm (2 to 10 arms)." });
      } else if (Math.abs(split.reduce((a, b) => a + b, 0) - 1) > 1e-6) {
        ctx.addIssue({ code: "custom", path: ["planned_split"], message: "The shares must add up to 1." });
      }
    }
  });

export type MappingFormInput = z.input<typeof mappingSchema>;
export type MappingFormValues = z.output<typeof mappingSchema>;

export function toMapping(v: MappingFormValues): Mapping {
  return {
    variant_col: v.variant_col,
    control_label: v.control_label.trim(),
    metric_col: v.metric_col,
    metric_type: v.metric_type,
    pre_period_col: v.pre_period_col || null,
    planned_split: parseSplit(v.planned_split),
    alpha: v.alpha,
  };
}

export const sampleSizeSchema = z
  .object({
    mode: z.enum(["n", "mde"]),
    base_rate: z.coerce.number({ error: "Enter a number." }).gt(0, "Must be above 0.").lt(1, "Must be below 1."),
    mde_abs: z.coerce.number({ error: "Enter a number." }),
    n_per_arm: z.coerce.number({ error: "Enter a number." }),
    alpha: z.coerce.number({ error: "Enter a number." }).gt(0, "Must be above 0.").lte(0.2, "At most 0.2."),
    power: z.coerce.number({ error: "Enter a number." }).gte(0.5, "At least 0.5.").lt(1, "Must be below 1."),
  })
  .superRefine((v, ctx) => {
    if (v.mode === "n" && !(v.mde_abs > 0 && v.mde_abs < 1)) {
      ctx.addIssue({ code: "custom", path: ["mde_abs"], message: "The lift must be between 0 and 1 (e.g. 0.01 = 1 point)." });
    }
    if (v.mode === "mde" && !(Number.isInteger(v.n_per_arm) && v.n_per_arm >= 2)) {
      ctx.addIssue({ code: "custom", path: ["n_per_arm"], message: "Enter a whole number of at least 2." });
    }
  });

export type SampleSizeInput = z.input<typeof sampleSizeSchema>;
export type SampleSizeValues = z.output<typeof sampleSizeSchema>;
