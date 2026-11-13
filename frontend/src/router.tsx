import { QueryClient } from "@tanstack/react-query";
import type { RouteObject } from "react-router";

import { Layout } from "./components/Layout";
import { AnalysisPage } from "./pages/AnalysisPage";
import { Home } from "./pages/Home";
import { Method } from "./pages/Method";
import { NewUpload } from "./pages/NewUpload";
import { NotFound } from "./pages/NotFound";
import { Reports } from "./pages/Reports";
import { SampleSize } from "./pages/SampleSize";

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/new", element: <NewUpload /> },
      { path: "/analyses/:id", element: <AnalysisPage /> },
      { path: "/sample-size", element: <SampleSize /> },
      { path: "/reports", element: <Reports /> },
      { path: "/method", element: <Method /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });
}
