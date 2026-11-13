import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router";

import { api } from "../api/client";
import { useCreateAnalysis } from "../api/queries";
import type { CompleteUploadResponse } from "../api/types";
import { checkFile, uploadToS3 } from "../api/upload";
import { int } from "../lib/format";
import { MappingForm } from "../components/MappingForm";
import { Card, ErrorMessage, Spinner } from "../components/ui";

type Phase = "idle" | "signing" | "uploading" | "checking" | "ready";

export function ProgressBar({ value }: { value: number }) {
  const pctValue = Math.round(value * 100);
  return (
    <div>
      <div
        role="progressbar"
        aria-label="Upload progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pctValue}
        className="h-3 w-full overflow-hidden rounded-full bg-stone-200"
      >
        <div className="h-full bg-teal-700 transition-[width] duration-150" style={{ width: `${String(pctValue)}%` }} />
      </div>
      <p className="mt-1 text-xs tabular-nums text-stone-600">{pctValue}% uploaded</p>
    </div>
  );
}

export function NewUpload() {
  const navigate = useNavigate();
  const create = useCreateAnalysis();
  const input = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [fileName, setFileName] = useState<string>("");
  const [dragging, setDragging] = useState(false);
  const [done, setDone] = useState<CompleteUploadResponse | null>(null);

  async function start(file: File) {
    setError(null);
    setDone(null);
    setProgress(0);
    setFileName(file.name);
    const problem = checkFile(file);
    if (problem) {
      setError(new Error(problem));
      setPhase("idle");
      return;
    }
    try {
      setPhase("signing");
      const signed = await api.createUpload(file.name, file.size);
      setPhase("uploading");
      await uploadToS3(signed.s3.url, signed.s3.fields, file, setProgress);
      setPhase("checking");
      setDone(await api.completeUpload(signed.upload_id));
      setPhase("ready");
    } catch (e) {
      setError(e);
      setPhase("idle");
    }
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) void start(f);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Analyze your own test</h1>
      <Card title="1. Upload a CSV">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => {
            setDragging(false);
          }}
          onDrop={onDrop}
          className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 text-center ${
            dragging ? "border-teal-600 bg-teal-50" : "border-stone-300 bg-stone-50"
          }`}
        >
          <p className="text-sm text-stone-700">Drag a .csv file here (up to 50 MB), or</p>
          <label className="cursor-pointer rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 focus-within:ring-2 focus-within:ring-teal-600 focus-within:ring-offset-2">
            Choose a file
            <input
              ref={input}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="CSV file to upload"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void start(f);
                e.target.value = "";
              }}
            />
          </label>
          <p className="text-xs text-stone-500">One row per user. Needs a column with the variant and a column with the outcome. The file goes straight to storage; our API never handles its bytes.</p>
        </div>
        <div className="mt-4 space-y-3">
          {fileName && phase !== "idle" ? <p className="text-sm font-medium">{fileName}</p> : null}
          {phase === "signing" ? <Spinner label="Preparing upload…" /> : null}
          {phase === "uploading" || phase === "checking" || phase === "ready" ? <ProgressBar value={progress} /> : null}
          {phase === "checking" ? <Spinner label="Checking the file…" /> : null}
          <ErrorMessage error={error} title="Upload failed" />
        </div>
      </Card>

      {done ? (
        <>
          <Card title={`2. Preview (first ${String(done.preview.length)} rows of ${fileName}, ${int(done.size_bytes)} bytes)`}>
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">First rows of the uploaded file</caption>
                <thead className="sticky top-0 bg-white">
                  <tr>
                    {done.columns.map((c) => (
                      <th key={c} scope="col" className="border-b border-stone-200 px-2 py-1 text-left font-semibold">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {done.preview.map((row, i) => (
                    <tr key={i} className="odd:bg-stone-50">
                      {row.map((v, j) => <td key={j} className="px-2 py-1 tabular-nums">{v}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <Card title="3. Map the columns">
            <MappingForm
              columns={done.columns}
              preview={done.preview}
              submitting={create.isPending}
              onSubmit={(mapping) => {
                create.mutate(
                  { uploadId: done.upload_id, mapping },
                  {
                    onSuccess: (r) => {
                      void navigate(`/analyses/${r.analysis_id}`);
                    },
                  },
                );
              }}
            />
            <div className="mt-4">
              <ErrorMessage error={create.error} title="Could not start the analysis" />
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
