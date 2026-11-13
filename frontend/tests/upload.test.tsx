import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { checkFile } from "../src/api/upload";
import { renderRoute } from "./render";
import { API, server } from "./server";

/** A fake XMLHttpRequest driven by the test: progress() emits an upload progress event, finish() completes. */
class FakeXhr {
  static last: FakeXhr | null = null;
  status = 0;
  responseText = "";
  method = "";
  url = "";
  body: FormData | null = null;
  upload: { onprogress: ((e: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  send(body: FormData) {
    this.body = body;
    FakeXhr.last = this;
  }

  progress(loaded: number) {
    act(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded, total: 100 } as ProgressEvent);
    });
  }

  finish(status: number) {
    act(() => {
      this.status = status;
      this.responseText = status === 400 ? "<Code>EntityTooLarge</Code>" : "";
      this.onload?.();
    });
  }
}

async function sentXhr(): Promise<FakeXhr> {
  await waitFor(() => {
    expect(FakeXhr.last).not.toBeNull();
  });
  const x = FakeXhr.last;
  if (!x) throw new Error("no XHR sent");
  return x;
}

const CSV = "user,group,converted\n1,control,0\n2,treatment,1\n";

function mockApi() {
  server.use(
    http.post(`${API}/uploads`, () =>
      HttpResponse.json(
        { upload_id: "u-1", s3: { url: "http://s3.test/bucket", fields: { key: "uploads/u-1.csv", policy: "p", "x-amz-signature": "s" } }, max_bytes: 52428800, expires_in: 600 },
        { status: 201 },
      ),
    ),
    http.post(`${API}/uploads/u-1/complete`, () =>
      HttpResponse.json({ upload_id: "u-1", size_bytes: CSV.length, columns: ["user", "group", "converted"], preview: [["1", "control", "0"], ["2", "treatment", "1"]] }),
    ),
    http.post(`${API}/analyses`, () => HttpResponse.json({ analysis_id: "a-1", status: "QUEUED" }, { status: 202 })),
    http.get(`${API}/analyses/a-1`, () => HttpResponse.json({ id: "a-1", status: "QUEUED", mapping: { metric_col: "converted", metric_type: "binary", variant_col: "group", control_label: "control" } })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeXhr.last = null;
});

describe("client-side file check", () => {
  it("accepts .csv up to 50 MB only", () => {
    expect(checkFile({ name: "a.csv", size: 10 })).toBeNull();
    expect(checkFile({ name: "a.xlsx", size: 10 })).toMatch(/Only .csv/);
    expect(checkFile({ name: "a.csv", size: 52_428_801 })).toMatch(/limit is 50 MB/);
    expect(checkFile({ name: "a.csv", size: 0 })).toMatch(/empty/);
  });
});

describe("upload page", () => {
  it("uploads to S3 with progress, shows the preview, and submits the mapping", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    mockApi();
    const user = userEvent.setup();
    const { router } = renderRoute("/new");
    const file = new File([CSV], "test.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("CSV file to upload"), file);

    const xhr = await sentXhr();
    const bar = await screen.findByRole("progressbar", { name: "Upload progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "0");
    xhr.progress(25);
    expect(bar).toHaveAttribute("aria-valuenow", "25");
    xhr.progress(60);
    expect(bar).toHaveAttribute("aria-valuenow", "60");
    xhr.progress(100);
    xhr.finish(204);
    await waitFor(() => {
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    });

    expect(FakeXhr.last?.method).toBe("POST");
    expect(FakeXhr.last?.url).toBe("http://s3.test/bucket");
    const keys = [...(FakeXhr.last?.body?.keys() ?? [])];
    expect(keys.at(-1)).toBe("file"); // the policy fields must come before the file
    expect(keys).toContain("policy");

    expect(await screen.findByRole("table", { name: "First rows of the uploaded file" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Metric column"), "converted");
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/analyses/a-1");
    });
  });

  it("shows S3's rejection when the file is too large for the policy", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    mockApi();
    const user = userEvent.setup();
    renderRoute("/new");
    await user.upload(screen.getByLabelText("CSV file to upload"), new File([CSV], "test.csv"));
    (await sentXhr()).finish(400);
    expect(await screen.findByText(/Storage rejected the file: it is over 50 MB/)).toBeInTheDocument();
  });

  it("shows the API's error message (415) and the client-side check", async () => {
    server.use(http.post(`${API}/uploads`, () => HttpResponse.json({ error: { code: "UNSUPPORTED_FILE_TYPE", message: "Only .csv files can be analyzed." } }, { status: 415 })));
    renderRoute("/new");
    const input = screen.getByLabelText("CSV file to upload");
    fireEvent.change(input, { target: { files: [new File(["x"], "data.xlsx")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Only .csv files can be analyzed.");
  });
});
