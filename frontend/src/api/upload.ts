import { ApiError } from "./client";

export const MAX_BYTES = 52_428_800;

/** Client-side check before asking for a presigned POST. Returns an error message or null. */
export function checkFile(file: Pick<File, "name" | "size">): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) return "Only .csv files can be analyzed.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_BYTES) return `The file is ${(file.size / 1_048_576).toFixed(1)} MB; the limit is 50 MB.`;
  return null;
}

/**
 * POST the file straight to S3 with the presigned fields. XMLHttpRequest (not fetch) so upload progress events
 * drive the progress bar. The file field must come last in the form, after the policy fields.
 */
export function uploadToS3(
  url: string,
  fields: Record<string, string>,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e: ProgressEvent) => {
      if (e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(1);
        resolve();
      } else {
        const tooLarge = xhr.responseText.includes("EntityTooLarge");
        reject(
          new ApiError(
            xhr.status,
            tooLarge ? "FILE_TOO_LARGE" : "S3_UPLOAD_FAILED",
            tooLarge ? "Storage rejected the file: it is over 50 MB." : `Storage rejected the upload (HTTP ${String(xhr.status)}).`,
          ),
        );
      }
    };
    xhr.onerror = () => {
      reject(new ApiError(0, "S3_UNREACHABLE", "Could not reach storage to upload the file. Check your connection."));
    };
    xhr.send(form);
  });
}
