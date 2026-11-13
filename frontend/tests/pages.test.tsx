import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./render";
import { API, fixtures, server } from "./server";

describe("home", () => {
  it("starts the sample analysis and navigates to it", async () => {
    server.use(http.post(`${API}/analyses/sample/hillstrom`, () => HttpResponse.json({ analysis_id: fixtures.visit.id, status: "QUEUED" }, { status: 202 })));
    server.use(http.get(`${API}/analyses/:id`, () => HttpResponse.json(fixtures.visit)));
    const user = userEvent.setup();
    const { router } = renderRoute("/");
    await user.click(screen.getByRole("button", { name: "Analyze a real 64,000-customer email test" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/analyses/${fixtures.visit.id}`);
    });
  });

  it("shows the rate-limit message from the API", async () => {
    server.use(
      http.post(`${API}/analyses/sample/hillstrom`, () =>
        HttpResponse.json({ error: { code: "RATE_LIMITED", message: "Too many analyses from your address; the limit is 30 per hour." } }, { status: 429 }),
      ),
    );
    const user = userEvent.setup();
    renderRoute("/");
    await user.click(screen.getByRole("button", { name: "Analyze a real 64,000-customer email test" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the limit is 30 per hour");
  });

  it("lists recent analyses", async () => {
    server.use(
      http.get(`${API}/analyses`, () =>
        HttpResponse.json({ results: [{ id: "a1", created_at: "2026-11-13T10:00:00Z", status: "SUCCEEDED", metric_col: "visit", metric_type: "binary", sample_name: "hillstrom", file_name: null, verdict: "Mens E-Mail increased visit rate.", reused_from: null }] }),
      ),
    );
    renderRoute("/");
    expect(await screen.findByText("Sample: hillstrom · visit")).toBeInTheDocument();
  });
});

describe("sample size", () => {
  it("solves for n and shows the result", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API}/sample-size`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ solved_for: "n_per_arm", n_per_arm: 14128, mde_abs: 0.01, base_rate: 0.1, alpha: 0.05, power: 0.8, curve: [{ n_per_arm: 3532, mde_abs: 0.02 }, { n_per_arm: 56512, mde_abs: 0.005 }] });
      }),
    );
    const user = userEvent.setup();
    renderRoute("/sample-size");
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(await screen.findByTestId("sample-size-result")).toHaveTextContent("You need 14,128 users per arm");
    expect(body).toEqual({ base_rate: 0.1, alpha: 0.05, power: 0.8, mde_abs: 0.01 });
  });

  it("switches to solving for the MDE and validates input", async () => {
    const user = userEvent.setup();
    renderRoute("/sample-size");
    await user.click(screen.getByLabelText("Minimum detectable effect"));
    const n = screen.getByLabelText("Users per arm");
    await user.clear(n);
    await user.type(n, "1");
    await user.click(screen.getByRole("button", { name: "Calculate" }));
    expect(await screen.findByText("Enter a whole number of at least 2.")).toBeInTheDocument();
  });
});

describe("reports", () => {
  it("renders both cards from the API with the source", async () => {
    renderRoute("/reports");
    expect(await screen.findByText("Churn model (UCI Online Retail II)")).toBeInTheDocument();
    expect(screen.getByText("Weekly revenue forecasting")).toBeInTheDocument();
    expect(screen.getByText(/Source: applied-data-science-lab/)).toBeInTheDocument();
    expect(screen.getByText(/Recalibration failed/)).toBeInTheDocument();
  });
});

describe("method", () => {
  it("documents the SRM threshold and the CUPED rule", () => {
    renderRoute("/method");
    expect(screen.getByText(/flagged when p < 0.001/)).toBeInTheDocument();
    expect(screen.getByText(/\|correlation\| ≥ 0.1 and at least 5% of the variance/)).toBeInTheDocument();
  });
});
