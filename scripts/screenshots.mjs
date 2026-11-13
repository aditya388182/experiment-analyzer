// Screenshots of every page against the running dev stack (Vite on 5173 -> API on 8000 -> worker, moto).
// Usage: PLAYWRIGHT_DIR=<dir with playwright installed> node scripts/screenshots.mjs [baseUrl] [outDir]
// Optional hooks between steps: STOP_WORKER_CMD / START_WORKER_CMD (shell commands) for the "queued" shot.
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(path.join(process.env.PLAYWRIGHT_DIR ?? ".", "package.json"));
const { chromium } = require("playwright");

const BASE = process.argv[2] ?? "http://localhost:5173";
const OUT = process.argv[3] ?? "docs/screenshots";
const CSV = path.resolve("backend/samples/hillstrom.csv");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
const page = await context.newPage();
const shot = async (name, opts = {}) => {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true, ...opts });
  console.log(`saved ${name}.png  (${page.url()})`);
};
const run = (cmd) => cmd && execSync(cmd, { stdio: "inherit", shell: "/bin/bash" });

// 1. Sample run for conversion (computed by the worker the first time; reused on later runs).
await page.goto(`${BASE}/`);
await page.getByLabel("Outcome").selectOption("conversion");
await page.getByRole("button", { name: "Analyze a real 64,000-customer email test" }).click();
await page.getByTestId("verdict").waitFor({ timeout: 30_000 });
await shot("03-analysis-sample-conversion");

// 2. Sample run for visit (the headline result); may be reused, which shows the provenance link.
await page.goto(`${BASE}/`);
await page.getByRole("button", { name: "Analyze a real 64,000-customer email test" }).click();
await page.getByTestId("verdict").waitFor({ timeout: 30_000 });
await shot("02-analysis-sample-visit");

// 3. Home with the recent list.
await page.goto(`${BASE}/`);
await page.getByRole("heading", { name: "Recent analyses" }).waitFor();
await page.getByText("Loading recent analyses…").waitFor({ state: "detached" });
await page.waitForTimeout(800);
await shot("01-home");

// 4. Real upload of the 3.9 MB CSV with upload bandwidth throttled so the progress bar is visible mid-way.
const cdp = await context.newCDPSession(page);
await cdp.send("Network.enable");
await cdp.send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 20,
  downloadThroughput: -1,
  uploadThroughput: 500 * 1024, // bytes/s -> about 8 s for the file
});
await page.goto(`${BASE}/new`);
await page.getByLabel("CSV file to upload").setInputFiles(CSV);
const bar = page.getByRole("progressbar", { name: "Upload progress" });
await bar.waitFor();
await page.waitForFunction(() => {
  const v = Number(document.querySelector("[role=progressbar]")?.getAttribute("aria-valuenow"));
  return v >= 30 && v <= 70;
}, null, { timeout: 30_000 });
await shot("04-upload-progress", { fullPage: false });
await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });

// 5. Preview + mapping form, filled in.
await page.getByRole("table", { name: "First rows of the uploaded file" }).waitFor({ timeout: 60_000 });
await page.getByLabel("Variant column").selectOption("segment");
await page.getByLabel("Control label").fill("No E-Mail");
await page.getByLabel("Metric column").selectOption("spend");
await page.getByLabel(/Continuous/).check();
await page.getByLabel("Pre-period column (optional)").selectOption("history");
await shot("05-upload-preview-mapping");

// 6. Submit with the worker stopped: the analysis waits in the queue (status timeline), then runs.
run(process.env.STOP_WORKER_CMD);
await page.getByLabel("Pre-period column (optional)").selectOption("");
await page.getByLabel("Significance level (alpha)").fill("0.1"); // new mapping hash -> a fresh job, not a reuse
await page.getByRole("button", { name: "Analyze" }).click();
await page.getByText("Waiting for a worker…").waitFor({ timeout: 15_000 });
await shot("06-analysis-queued", { fullPage: false });
run(process.env.START_WORKER_CMD);
await page.getByTestId("verdict").waitFor({ timeout: 60_000 });
await shot("07-analysis-upload-spend");

// 7. A failed analysis (bad data): upload a one-arm file through the UI.
const oneArm = path.resolve(process.env.ONE_ARM_CSV ?? "one_arm.csv");
await page.goto(`${BASE}/new`);
await page.getByLabel("CSV file to upload").setInputFiles(oneArm);
await page.getByRole("table", { name: "First rows of the uploaded file" }).waitFor({ timeout: 30_000 });
await page.getByLabel("Variant column").selectOption("group");
await page.getByLabel("Control label").fill("A");
await page.getByLabel("Metric column").selectOption("y");
await page.getByRole("button", { name: "Analyze" }).click();
await page.getByText("The analysis could not run").waitFor({ timeout: 30_000 });
await shot("08-analysis-failed");

// 8. Sample size (solve for n), reports, method.
await page.goto(`${BASE}/sample-size`);
await page.getByRole("button", { name: "Calculate" }).click();
await page.getByTestId("sample-size-result").waitFor();
await page.waitForTimeout(500);
await shot("09-sample-size");

await page.goto(`${BASE}/reports`);
await page.getByText("Weekly revenue forecasting").waitFor();
await page.waitForTimeout(500);
await shot("10-model-reports");

await page.goto(`${BASE}/method`);
await shot("11-method");

await browser.close();
