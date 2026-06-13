import Link from "next/link";
import { redirect } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { connectBroker } from "@/lib/engine";
import { getAccessToken } from "@/lib/supabase/server";

/** Upstox redirects here with ?code=...&state=... after the user authorizes. */
export default async function BrokerCallbackPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string; state?: string; error?: string }>;
}) {
  const { code, state, error } = await searchParams;

  if (error) return <Result ok={false} message={`Upstox returned an error: ${error}`} />;
  if (!code) return <Result ok={false} message="No authorization code returned by Upstox." />;

  const token = await getAccessToken();
  if (!token) redirect("/login?next=/onboarding");

  const result = await connectBroker(token, code, state);
  if (!result.ok) {
    return <Result ok={false} message={result.error ?? "Failed to connect broker."} />;
  }
  return <Result ok message="Upstox connected. Your positions are now read-only accessible." />;
}

function Result({ ok, message }: { ok: boolean; message: string }) {
  return (
    <div className="mx-auto max-w-md py-10">
      <Card>
        <CardHeader>
          <CardTitle>{ok ? "Broker connected ✅" : "Connection failed"}</CardTitle>
          <CardDescription>{message}</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Link href="/" className={buttonVariants()}>
            Go to dashboard
          </Link>
          {!ok && (
            <Link href="/onboarding" className={buttonVariants({ variant: "outline" })}>
              Try again
            </Link>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
