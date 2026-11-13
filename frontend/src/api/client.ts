import type {
  AnalysisDetail,
  AnalysisList,
  ApiErrorBody,
  CompleteUploadResponse,
  CreateAnalysisResponse,
  CreateUploadResponse,
  Mapping,
  Reports,
  SampleSizeRequest,
  SampleSizeResponse,
} from "./types";

const BASE: string = import.meta.env.VITE_API_BASE_URL ?? "";

/** Every failed request becomes an ApiError carrying the server's code and message, shown to the user. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isErrorBody(x: unknown): x is ApiErrorBody {
  if (typeof x !== "object" || x === null || !("error" in x)) return false;
  const e = x.error;
  return typeof e === "object" && e !== null && "code" in e && "message" in e;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Could not reach the server. Check your connection and try again.");
  }
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    if (isErrorBody(body)) throw new ApiError(res.status, body.error.code, body.error.message);
    throw new ApiError(res.status, "HTTP_" + String(res.status), `The server answered ${String(res.status)} ${res.statusText}.`);
  }
  return body as T;
}

const post = <T>(path: string, data?: unknown) =>
  request<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });

export const api = {
  getAnalysis: (id: string) => request<AnalysisDetail>(`/api/analyses/${encodeURIComponent(id)}`),
  listAnalyses: (limit = 20) => request<AnalysisList>(`/api/analyses?limit=${String(limit)}`),
  createSample: (metric_col: "visit" | "conversion" | "spend") =>
    post<CreateAnalysisResponse>("/api/analyses/sample/hillstrom", { metric_col }),
  createAnalysis: (upload_id: string, mapping: Mapping) =>
    post<CreateAnalysisResponse>("/api/analyses", { upload_id, mapping }),
  createUpload: (filename: string, size: number) => post<CreateUploadResponse>("/api/uploads", { filename, size }),
  completeUpload: (id: string) => post<CompleteUploadResponse>(`/api/uploads/${encodeURIComponent(id)}/complete`),
  sampleSize: (req: SampleSizeRequest) => post<SampleSizeResponse>("/api/sample-size", req),
  reports: () => request<Reports>("/api/reports"),
};
