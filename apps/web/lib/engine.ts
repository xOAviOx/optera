import "server-only";

import { ENGINE_URL } from "./utils";

export interface BrokerStatus {
  connected: boolean;
  broker: string;
  status: string | null;
  expires_at: string | null;
  reconnect_needed: boolean;
  has_analytics_token: boolean;
}

/** Server-side authenticated fetch to the engine (Bearer = Supabase access token). */
async function engineFetch(path: string, accessToken: string, init?: RequestInit) {
  return fetch(`${ENGINE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function getBrokerStatus(accessToken: string): Promise<BrokerStatus | null> {
  try {
    const res = await engineFetch("/broker/status", accessToken);
    if (!res.ok) return null;
    return (await res.json()) as BrokerStatus;
  } catch {
    return null;
  }
}

export async function getUpstoxLoginUrl(accessToken: string): Promise<string | null> {
  try {
    const res = await engineFetch("/broker/upstox/login-url", accessToken);
    if (!res.ok) return null;
    return ((await res.json()) as { url: string }).url;
  } catch {
    return null;
  }
}

export async function connectBroker(
  accessToken: string,
  code: string,
  state?: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await engineFetch("/auth/broker/connect", accessToken, {
      method: "POST",
      body: JSON.stringify({ code, state }),
    });
    if (!res.ok) return { ok: false, error: `Engine returned ${res.status}` };
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}
