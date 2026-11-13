import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { pollInterval } from "../src/api/queries";
import type { AnalysisDetail } from "../src/api/types";
import { renderRoute } from "./render";
import { API, fixtures, server } from "./server";

const visit = fixtures.visit as unknown as AnalysisDetail;

describe("pollInterval", () => {
  it("polls every second until a terminal state, then stops", () => {
    expect(pollInterval(undefined)).toBe(1000);
    expect(pollInterval({ ...visit, status: "QUEUED" })).toBe(1000);
    expect(pollInterval({ ...visit, status: "RUNNING" })).toBe(1000);
    expect(pollInterval({ ...visit, status: "SUCCEEDED" })).toBe(false);
    expect(pollInterval({ ...visit, status: "FAILED" })).toBe(false);
  });
});

describe("analysis page", () => {
  it("polls through QUEUED and RUNNING, renders the result, then stops polling", async () => {
    let calls = 0;
    server.use(
      http.get(`${API}/analyses/:id`, () => {
        calls += 1;
        if (calls === 1) return HttpResponse.json({ ...visit, status: "QUEUED", result: null });
        if (calls === 2) return HttpResponse.json({ ...visit, status: "RUNNING", result: null });
        return HttpResponse.json(visit);
      }),
    );
    renderRoute(`/analyses/${visit.id}`);
    expect(await screen.findByText("Waiting for a worker…")).toBeInTheDocument();
    expect(await screen.findByText("Analyzing the file…", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByTestId("verdict", {}, { timeout: 3000 })).toBeInTheDocument();
    const settled = calls;
    expect(settled).toBe(3);
    await new Promise((r) => setTimeout(r, 2200));
    expect(calls).toBe(settled);
  }, 10_000);

  it("shows the verdict, a green SRM banner and the CUPED message from a real result", async () => {
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(visit)));
    renderRoute(`/analyses/${visit.id}`);
    const verdict = await screen.findByTestId("verdict");
    expect(verdict).toHaveTextContent(visit.result?.verdict ?? "missing");
    expect(verdict).toHaveTextContent("7.66 percentage points (95% CI 7.00 to 8.32)");
    const banner = screen.getByRole("status", { name: "" });
    expect(within(banner).getByText("Traffic split looks healthy")).toBeInTheDocument();
    expect(screen.getByTestId("cuped-message")).toHaveTextContent("CUPED not helpful here");
    expect(screen.getByRole("table", { name: /arms and comparisons/i })).toBeInTheDocument();
    expect(screen.getByText(/could detect differences of/i)).toHaveTextContent("0.84 pts");
    expect(screen.getByRole("button", { name: "Copy link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeInTheDocument();
  });

  it("shows a red SRM alert with text (not just color) when the split is off", async () => {
    const r = visit.result;
    if (!r) throw new Error("fixture has no result");
    const flagged = { ...visit, result: { ...r, srm: { ...r.srm, p: 2e-9, flagged: true }, verdict: "Do not trust this result: the traffic split is off (SRM p = 2.0e-09). Rest." } };
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(flagged)));
    renderRoute(`/analyses/${visit.id}`);
    const alert = await screen.findByText("Traffic split check failed (sample ratio mismatch)");
    expect(alert.closest("[role=alert]")).toHaveTextContent("SRM p = 2.0e-9");
    expect(screen.getByTestId("verdict")).toHaveTextContent(/^Do not trust this result/);
  });

  it("shows CUPED adjusted results when CUPED helped", async () => {
    const r = visit.result;
    if (!r) throw new Error("fixture has no result");
    const helped = {
      ...visit,
      result: { ...r, cuped: { ...r.cuped, helpful: true, corr: 0.6, variance_removed: 0.36, message: "CUPED helpful (correlation 0.60, variance removed 36.0%); adjusted intervals are shown.", adjusted: r.comparisons } },
    };
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(helped)));
    renderRoute(`/analyses/${visit.id}`);
    expect(await screen.findByTestId("cuped-message")).toHaveTextContent("CUPED helpful");
    expect(screen.getByText("36.00%")).toBeInTheDocument();
    expect(screen.getByText(/^Mens E-Mail: 7.66 pts \(CI/)).toBeInTheDocument();
  });

  it("explains a failed analysis and what to fix", async () => {
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(fixtures.failed)));
    renderRoute(`/analyses/x`);
    expect(await screen.findByText("The analysis could not run")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Found 1 arm(s)");
    expect(screen.getByRole("alert")).toHaveTextContent("(SINGLE_ARM)");
    expect(screen.getByText(/What to fix:/)).toBeInTheDocument();
  });

  it("shows the API error when the analysis does not exist", async () => {
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json({ error: { code: "NOT_FOUND", message: "Analysis not found." } }, { status: 404 })));
    renderRoute(`/analyses/nope`);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Analysis not found.");
    expect(alert).toHaveTextContent("NOT_FOUND");
  });

  it("renders continuous results in metric units with relative lift", async () => {
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(fixtures.spend)));
    renderRoute(`/analyses/x`);
    expect(await screen.findByTestId("verdict")).toHaveTextContent("increased spend by 0.770 (95% CI 0.485 to 1.055; +117.9% relative)");
  });
});

describe("forest plot ticks", () => {
  it("uses round steps and includes zero", async () => {
    const { niceTicks } = await import("../src/lib/ticks");
    expect(niceTicks(0, 0.83)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
    expect(niceTicks(-3, 2)).toContain(0);
    expect(niceTicks(0.15, 8.3)).toEqual([0, 2, 4, 6, 8, 10]);
  });
});
