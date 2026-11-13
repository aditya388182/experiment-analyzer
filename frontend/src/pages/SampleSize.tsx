import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api/client";
import type { SampleSizeRequest } from "../api/types";
import { int } from "../lib/format";
import { sampleSizeSchema, type SampleSizeInput, type SampleSizeValues } from "../lib/schemas";
import { Button, Card, ErrorMessage, FieldError, inputClass } from "../components/ui";

export function SampleSize() {
  const calc = useMutation({ mutationFn: api.sampleSize });
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<SampleSizeInput, unknown, SampleSizeValues>({
    resolver: zodResolver(sampleSizeSchema),
    defaultValues: { mode: "n", base_rate: 0.1, mde_abs: 0.01, n_per_arm: 20000, alpha: 0.05, power: 0.8 },
  });
  const mode = useWatch({ control, name: "mode" });

  const submit = (v: SampleSizeValues) => {
    const req: SampleSizeRequest = { base_rate: v.base_rate, alpha: v.alpha, power: v.power };
    if (v.mode === "n") req.mde_abs = v.mde_abs;
    else req.n_per_arm = v.n_per_arm;
    calc.mutate(req);
  };

  const field = (name: keyof SampleSizeInput) => ({
    id: `s-${name}`,
    inputMode: "decimal" as const,
    "aria-invalid": errors[name] ? true : undefined,
    "aria-describedby": errors[name] ? `se-${name}` : undefined,
    className: inputClass,
  });
  const r = calc.data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sample size calculator</h1>
      <p className="max-w-2xl text-sm text-stone-700">
        For a conversion-style (0/1) metric with two equal arms and a two-sided test. Solve for the users you need per arm, or for
        the smallest lift a given sample can detect.
      </p>
      <Card>
        <form
          noValidate
          aria-label="Sample size inputs"
          className="grid gap-4 sm:grid-cols-3"
          onSubmit={(e) => {
            void handleSubmit(submit)(e);
          }}
        >
          <fieldset className="sm:col-span-3">
            <legend className="text-sm font-medium">Solve for</legend>
            <div className="mt-2 flex gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input type="radio" value="n" {...register("mode")} /> Sample size (users per arm needed)
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" value="mde" {...register("mode")} /> Minimum detectable effect
              </label>
            </div>
          </fieldset>
          <div>
            <label htmlFor="s-base_rate" className="text-sm font-medium">Baseline rate</label>
            <input {...register("base_rate")} {...field("base_rate")} />
            <FieldError id="se-base_rate" message={errors.base_rate?.message} />
          </div>
          {mode === "n" ? (
            <div>
              <label htmlFor="s-mde_abs" className="text-sm font-medium">Lift to detect (absolute)</label>
              <input {...register("mde_abs")} {...field("mde_abs")} />
              <p className="mt-1 text-xs text-stone-500">0.01 = one percentage point.</p>
              <FieldError id="se-mde_abs" message={errors.mde_abs?.message} />
            </div>
          ) : (
            <div>
              <label htmlFor="s-n_per_arm" className="text-sm font-medium">Users per arm</label>
              <input {...register("n_per_arm")} {...field("n_per_arm")} inputMode="numeric" />
              <FieldError id="se-n_per_arm" message={errors.n_per_arm?.message} />
            </div>
          )}
          <div>
            <label htmlFor="s-alpha" className="text-sm font-medium">Alpha</label>
            <input {...register("alpha")} {...field("alpha")} />
            <FieldError id="se-alpha" message={errors.alpha?.message} />
          </div>
          <div>
            <label htmlFor="s-power" className="text-sm font-medium">Power</label>
            <input {...register("power")} {...field("power")} />
            <FieldError id="se-power" message={errors.power?.message} />
          </div>
          <div className="flex items-end sm:col-span-3">
            <Button type="submit" disabled={calc.isPending}>Calculate</Button>
          </div>
        </form>
        <div className="mt-4">
          <ErrorMessage error={calc.error} title="Could not calculate" />
        </div>
      </Card>

      {r ? (
        <Card title="Result">
          <p className="text-lg" data-testid="sample-size-result">
            {r.solved_for === "n_per_arm" ? (
              <>
                You need <strong className="tabular-nums">{int(r.n_per_arm)}</strong> users per arm ({int(r.n_per_arm * 2)} total) to detect a{" "}
                {(r.mde_abs * 100).toFixed(2)} point lift from {(r.base_rate * 100).toFixed(1)}%.
              </>
            ) : (
              <>
                With {int(r.n_per_arm)} users per arm you can detect lifts of{" "}
                <strong className="tabular-nums">{(r.mde_abs * 100).toFixed(2)} percentage points</strong> or more.
              </>
            )}
          </p>
          <div className="mt-4" style={{ width: "100%", height: 280 }} role="img" aria-label="Detectable lift by users per arm">
            <ResponsiveContainer>
              <LineChart data={r.curve.map((p) => ({ n: p.n_per_arm, mde: p.mde_abs * 100 }))} margin={{ top: 10, right: 20, bottom: 24, left: 10 }}>
                <CartesianGrid stroke="#e7e5e4" />
                <XAxis
                  dataKey="n"
                  type="number"
                  scale="log"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(v: number) => int(Math.round(v))}
                  label={{ value: "users per arm (log scale)", position: "insideBottom", offset: -14, fontSize: 12 }}
                  fontSize={12}
                />
                <YAxis tickFormatter={(v: number) => v.toFixed(2)} label={{ value: "detectable lift (pts)", angle: -90, position: "insideLeft", fontSize: 12 }} fontSize={12} />
                <Tooltip formatter={(v) => [`${Number(v).toFixed(3)} pts`, "MDE"]} labelFormatter={(n) => `${int(Number(n))} per arm`} />
                <Line type="monotone" dataKey="mde" stroke="#0f766e" dot={false} isAnimationActive={false} />
                <ReferenceDot x={r.n_per_arm} y={r.mde_abs * 100} r={5} fill="#134e4a" stroke="white" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
