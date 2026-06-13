export { cn } from "@optera/ui";

/** ₹ formatting with Indian grouping (lakh/crore). */
export function formatRupees(value: number, opts?: { decimals?: number }): string {
  const decimals = opts?.decimals ?? 0;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

export const ENGINE_URL = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";
export const ENGINE_WS_URL = process.env.NEXT_PUBLIC_ENGINE_WS_URL ?? "ws://localhost:8000";
