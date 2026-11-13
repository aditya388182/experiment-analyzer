import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" }); // msw 3 renamed onUnhandledRequest
});
afterEach(() => {
  // Unmount first: a page still polling (e.g. /analyses/:id) must not fire after its handlers are reset.
  cleanup();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});
