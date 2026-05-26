import { QueryClient } from "@tanstack/react-query";
import { AuthRequiredError } from "./api-client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, error) => {
        if (error instanceof AuthRequiredError) return false;
        return failureCount < 3;
      },
    },
  },
});
