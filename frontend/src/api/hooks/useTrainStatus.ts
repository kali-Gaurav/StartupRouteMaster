/**
 * Live train status hook – cached and deduplicated by train number.
 */

import { useQuery } from "@tanstack/react-query";
import { getTrainStatusApi } from "@/services/railwayBackApi";

export const TRAIN_STATUS_QUERY_KEY = "train-status";

export function useTrainStatus(trainNumber: string, enabled: boolean = true) {
  return useQuery({
    queryKey: [TRAIN_STATUS_QUERY_KEY, trainNumber],
    queryFn: () => getTrainStatusApi(trainNumber),
    enabled: enabled && !!trainNumber,
    staleTime: 1000 * 30, // 30 seconds – live status updates frequently
    gcTime: 1000 * 60 * 5, // 5 minutes
    refetchInterval: 1000 * 60, // Auto-refresh every minute
  });
}
