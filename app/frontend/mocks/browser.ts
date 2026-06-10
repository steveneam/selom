import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

// Browser-side MSW worker. Started lazily by app/msw-provider.tsx only when
// NEXT_PUBLIC_API_MOCKING === "enabled" (the `dev:mock` script), so the default
// `dev` run still hits the real backend proxy.
export const worker = setupWorker(...handlers);
