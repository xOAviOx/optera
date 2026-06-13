import type { HealthResponse } from "@optera/types";

import { ENGINE_URL } from "./utils";

/** Thin typed client for the engine. Expand per module. */
export async function getEngineHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${ENGINE_URL}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as HealthResponse;
  } catch {
    return null;
  }
}
