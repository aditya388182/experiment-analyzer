import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import failed from "./fixtures/analysis_failed.json";
import spend from "./fixtures/analysis_spend.json";
import visit from "./fixtures/analysis_visit.json";
import reports from "./fixtures/reports.json";

export const API = "http://localhost/api";
export const fixtures = { visit, spend, failed, reports };

export const server = setupServer(
  http.get(`${API}/analyses`, () => HttpResponse.json({ results: [] })),
  http.get(`${API}/reports`, () => HttpResponse.json(reports)),
);
