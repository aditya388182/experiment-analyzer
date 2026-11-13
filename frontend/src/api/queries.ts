import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import { isTerminal, type AnalysisDetail, type Mapping } from "./types";

export const keys = {
  analysis: (id: string) => ["analysis", id] as const,
  analyses: ["analyses"] as const,
  reports: ["reports"] as const,
};

/** Poll every second until the analysis reaches SUCCEEDED or FAILED, then stop. */
export const pollInterval = (data: AnalysisDetail | undefined): number | false => (isTerminal(data) ? false : 1000);

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: keys.analysis(id),
    queryFn: () => api.getAnalysis(id),
    refetchInterval: (q) => pollInterval(q.state.data),
    retry: (count, err) => !("status" in err && err.status === 404) && count < 2,
  });
}

export function useRecentAnalyses() {
  return useQuery({ queryKey: keys.analyses, queryFn: () => api.listAnalyses(20), refetchInterval: 5000 });
}

export function useReports() {
  return useQuery({ queryKey: keys.reports, queryFn: api.reports, staleTime: Infinity });
}

export function useCreateSample() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createSample,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.analyses }),
  });
}

export function useCreateAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ uploadId, mapping }: { uploadId: string; mapping: Mapping }) => api.createAnalysis(uploadId, mapping),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.analyses }),
  });
}

export type { AnalysisDetail };
