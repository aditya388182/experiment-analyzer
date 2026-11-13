// Frames of a real sample run for the README GIF. Usage:
//   PLAYWRIGHT_DIR=<dir with playwright> node scripts/record_gif.mjs <baseUrl> <framesDir> [metric]
// then: python scripts/make_gif.py <framesDir> docs/sample-run.gif
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(path.join(process.env.PLAYWRIGHT_DIR ?? ".", "package.json"));
const { chromium } = require("playwright");
const [base = "http://127.0.0.1:8081", out = "frames", metric = "conversion"] = process.argv.slice(2);
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 720 } });
let n = 0;
const frame = async (holdMs = 0) => {
  await page.screenshot({ path: path.join(out, `${String(n++).padStart(4, "0")}_${holdMs}.png`) });
};

await page.goto(`${base}/`);
await page.getByRole("heading", { name: "Recent analyses" }).waitFor();
await page.getByText("Loading recent analyses…").waitFor({ state: "detached" });
await frame(1500);
await page.getByLabel("Outcome").selectOption(metric);
await frame(800);
await page.getByRole("button", { name: "Analyze a real 64,000-customer email test" }).hover();
await frame(500);
await page.getByRole("button", { name: "Analyze a real 64,000-customer email test" }).click();
// Capture the status timeline as it moves, then the result.
const t0 = Date.now();
while (Date.now() - t0 < 15_000) {
  await frame(0);
  if (await page.getByTestId("verdict").isVisible().catch(() => false)) break;
  await page.waitForTimeout(80);
}
await frame(2500);
for (const y of [350, 700, 1050, 1400]) {
  await page.mouse.wheel(0, 350);
  await page.waitForTimeout(250);
  await frame(y === 1400 ? 2500 : 1200);
}
await browser.close();
console.log(`${n} frames in ${out}`);
