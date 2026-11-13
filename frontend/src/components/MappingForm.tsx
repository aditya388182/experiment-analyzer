import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";

import type { Mapping } from "../api/types";
import { mappingSchema, toMapping, type MappingFormInput, type MappingFormValues } from "../lib/schemas";
import { Button, FieldError, inputClass } from "./ui";

interface Props {
  columns: string[];
  preview: string[][];
  onSubmit: (mapping: Mapping) => void;
  submitting?: boolean;
}

function distinct(preview: string[][], col: number): string[] {
  if (col < 0) return [];
  return [...new Set(preview.map((r) => (r[col] ?? "").trim()).filter(Boolean))].sort();
}

/** Guess sensible defaults from the header and preview rows; the user can change all of them. */
function guess(columns: string[], preview: string[][]): MappingFormInput {
  const lower = columns.map((c) => c.toLowerCase());
  const pick = (re: RegExp) => columns[lower.findIndex((c) => re.test(c))] ?? "";
  const variant = pick(/variant|group|arm|segment|treatment|bucket/);
  const values = distinct(preview, columns.indexOf(variant));
  const control = values.find((v) => /control|no[\s_-]?e?-?mail|^a$|baseline/i.test(v)) ?? "";
  return {
    variant_col: variant,
    control_label: control,
    metric_col: "",
    metric_type: "binary",
    pre_period_col: "",
    planned_split: "",
    alpha: 0.05,
  };
}

export function MappingForm({ columns, preview, onSubmit, submitting = false }: Props) {
  const defaults = useMemo(() => guess(columns, preview), [columns, preview]);
  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors },
  } = useForm<MappingFormInput, unknown, MappingFormValues>({ resolver: zodResolver(mappingSchema), defaultValues: defaults });

  const [variantCol, metricCol, controlLabel] = useWatch({ control, name: ["variant_col", "metric_col", "control_label"] });
  const labels = useMemo(() => distinct(preview, columns.indexOf(variantCol)), [preview, columns, variantCol]);
  const splitOrder = useMemo(() => {
    const others = labels.filter((l) => l !== controlLabel.trim());
    return controlLabel.trim() ? [controlLabel.trim(), ...others] : labels;
  }, [labels, controlLabel]);

  // Suggest the metric type from the preview, only when it is unambiguous: any value other than 0/1 means
  // continuous; both 0 and 1 (and nothing else) means binary. An all-zero preview (e.g. spend, which is mostly 0)
  // says nothing, so the current choice is kept.
  useEffect(() => {
    const idx = columns.indexOf(metricCol);
    if (idx < 0) return;
    const vals = new Set(preview.map((r) => (r[idx] ?? "").trim()).filter(Boolean));
    if ([...vals].some((v) => v !== "0" && v !== "1")) setValue("metric_type", "continuous");
    else if (vals.has("0") && vals.has("1")) setValue("metric_type", "binary");
  }, [metricCol, columns, preview, setValue]);

  const field = (name: keyof MappingFormInput) => ({
    id: `f-${name}`,
    "aria-invalid": errors[name] ? true : undefined,
    "aria-describedby": errors[name] ? `e-${name}` : `h-${name}`,
  });

  return (
    <form
      noValidate
      aria-label="Column mapping"
      className="grid gap-5 sm:grid-cols-2"
      onSubmit={(e) => {
        void handleSubmit((v) => {
          onSubmit(toMapping(v));
        })(e);
      }}
    >
      <div>
        <label htmlFor="f-variant_col" className="text-sm font-medium">Variant column</label>
        <select {...register("variant_col")} {...field("variant_col")} className={inputClass}>
          <option value="">Choose…</option>
          {columns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <p id="h-variant_col" className="mt-1 text-xs text-stone-500">Which arm each row was assigned to.</p>
        <FieldError id="e-variant_col" message={errors.variant_col?.message} />
      </div>

      <div>
        <label htmlFor="f-control_label" className="text-sm font-medium">Control label</label>
        <input {...register("control_label")} {...field("control_label")} list="control-options" className={inputClass} autoComplete="off" />
        <datalist id="control-options">
          {labels.map((l) => <option key={l} value={l} />)}
        </datalist>
        <p id="h-control_label" className="mt-1 text-xs text-stone-500">
          Values seen in the preview: {labels.length ? labels.join(", ") : "pick a variant column first"}.
        </p>
        <FieldError id="e-control_label" message={errors.control_label?.message} />
      </div>

      <div>
        <label htmlFor="f-metric_col" className="text-sm font-medium">Metric column</label>
        <select {...register("metric_col")} {...field("metric_col")} className={inputClass}>
          <option value="">Choose…</option>
          {columns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <p id="h-metric_col" className="mt-1 text-xs text-stone-500">The outcome you want to compare.</p>
        <FieldError id="e-metric_col" message={errors.metric_col?.message} />
      </div>

      <fieldset>
        <legend className="text-sm font-medium">Metric type</legend>
        <div className="mt-2 flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" value="binary" {...register("metric_type")} /> Binary (0/1, e.g. converted)
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" value="continuous" {...register("metric_type")} /> Continuous (e.g. revenue)
          </label>
        </div>
      </fieldset>

      <div>
        <label htmlFor="f-pre_period_col" className="text-sm font-medium">Pre-period column (optional)</label>
        <select {...register("pre_period_col")} {...field("pre_period_col")} className={inputClass}>
          <option value="">None (skip CUPED)</option>
          {columns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <p id="h-pre_period_col" className="mt-1 text-xs text-stone-500">A pre-experiment value for each row, used for CUPED.</p>
        <FieldError id="e-pre_period_col" message={errors.pre_period_col?.message} />
      </div>

      <div>
        <label htmlFor="f-planned_split" className="text-sm font-medium">Planned split (optional)</label>
        <input {...register("planned_split")} {...field("planned_split")} placeholder="equal split" className={inputClass} />
        <p id="h-planned_split" className="mt-1 text-xs text-stone-500">
          Shares that sum to 1, in this order: {splitOrder.length ? splitOrder.join(", ") : "control first, then the others A→Z"}.
          Leave empty for an equal split.
        </p>
        <FieldError id="e-planned_split" message={errors.planned_split?.message} />
      </div>

      <div>
        <label htmlFor="f-alpha" className="text-sm font-medium">Significance level (alpha)</label>
        <input {...register("alpha")} {...field("alpha")} inputMode="decimal" className={inputClass} />
        <p id="h-alpha" className="mt-1 text-xs text-stone-500">0.05 gives 95% confidence intervals. Max 0.2.</p>
        <FieldError id="e-alpha" message={errors.alpha?.message} />
      </div>

      <div className="flex items-end sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Starting…" : "Analyze"}
        </Button>
      </div>
    </form>
  );
}
