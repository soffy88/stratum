"use client";

import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/query-client";
import { getTheme } from "@/lib/theme";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  // Restore the user-chosen theme from localStorage.
  // layout.tsx is a Server Component and statically renders data-theme="zen";
  // this effect runs once on the client after hydration to apply the saved value.
  useEffect(() => {
    const saved = getTheme();
    if (saved !== "zen") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="bottom-right" />
    </QueryClientProvider>
  );
}
