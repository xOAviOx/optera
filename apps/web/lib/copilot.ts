/**
 * Client for the AI co-pilot endpoint (POST /ai/chat).
 *
 * Runs in the browser, so it pulls the Supabase access token from the client
 * session and sends it as a Bearer token (the engine verifies it). The current
 * strategy is sent as context so the co-pilot's tools can analyze it.
 */
import { createClient } from "./supabase/client";
import { type WireLeg } from "./quant";
import { ENGINE_URL } from "./utils";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface StrategyContextPayload {
  legs: WireLeg[];
  spot: number;
  iv_pct: number;
  dte: number;
}

export interface ChatReply {
  reply: string;
  flagged: boolean;
}

export async function sendChat(
  messages: ChatMessage[],
  context: StrategyContextPayload | null,
): Promise<ChatReply> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) throw new Error("Please sign in again — your session expired.");

  const res = await fetch(`${ENGINE_URL}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ messages, context }),
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 503) throw new Error("AI is not configured on the server yet.");
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Engine returned ${res.status}`);
  }
  return (await res.json()) as ChatReply;
}
