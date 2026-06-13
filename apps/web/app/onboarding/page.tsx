import { redirect } from "next/navigation";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getBrokerStatus, getUpstoxLoginUrl } from "@/lib/engine";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient, getAccessToken } from "@/lib/supabase/server";

// Auth- and broker-state dependent: never statically cache.
export const dynamic = "force-dynamic";

const LANGUAGES = [
  { value: "hinglish", label: "Hinglish" },
  { value: "english", label: "English" },
  { value: "hindi", label: "हिंदी" },
];

export default async function OnboardingPage() {
  if (!isSupabaseConfigured) {
    return (
      <NotConfigured />
    );
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login?next=/onboarding");

  const { data: profile } = await supabase
    .from("profiles")
    .select("risk_disclosure_accepted_at, language_pref")
    .eq("id", user.id)
    .single();

  const token = await getAccessToken();
  const broker = token ? await getBrokerStatus(token) : null;

  const disclosureAccepted = Boolean(profile?.risk_disclosure_accepted_at);
  const language = profile?.language_pref ?? "hinglish";
  const brokerConnected = Boolean(broker?.connected);

  // ── Server actions ──────────────────────────────────────────────────────────
  async function acceptDisclosure() {
    "use server";
    const sb = await createClient();
    const {
      data: { user },
    } = await sb.auth.getUser();
    if (!user) return;
    await sb
      .from("profiles")
      .update({ risk_disclosure_accepted_at: new Date().toISOString() })
      .eq("id", user.id);
    redirect("/onboarding");
  }

  async function setLanguage(formData: FormData) {
    "use server";
    const sb = await createClient();
    const {
      data: { user },
    } = await sb.auth.getUser();
    if (!user) return;
    const lang = String(formData.get("language") ?? "hinglish");
    await sb.from("profiles").update({ language_pref: lang }).eq("id", user.id);
    redirect("/onboarding");
  }

  async function connectUpstox() {
    "use server";
    const tok = await getAccessToken();
    if (!tok) redirect("/login?next=/onboarding");
    const url = await getUpstoxLoginUrl(tok);
    if (!url) redirect("/onboarding?broker_error=1");
    redirect(url); // off to Upstox's authorize dialog
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome — let&apos;s set you up</h1>
        <p className="text-sm text-muted-foreground">Three quick steps to your live risk view.</p>
      </div>

      <Step
        n={1}
        done={disclosureAccepted}
        title="Risk disclosure"
        desc="Optera is an analytics & education tool. It explains and monitors risk — it never gives buy/sell advice and is not SEBI-registered."
      >
        {disclosureAccepted ? (
          <p className="text-sm text-primary">Accepted ✓</p>
        ) : (
          <form action={acceptDisclosure}>
            <Disclaimer className="mb-3" />
            <Button type="submit">I understand &amp; accept</Button>
          </form>
        )}
      </Step>

      <Step n={2} done title="Language" desc="Alerts and explanations default to this language.">
        <form action={setLanguage} className="flex items-center gap-3">
          <select
            name="language"
            defaultValue={language}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
          <Button type="submit" variant="outline">
            Save
          </Button>
        </form>
      </Step>

      <Step
        n={3}
        done={brokerConnected}
        title="Connect Upstox (read-only)"
        desc="Reads your live F&O positions. No orders are ever placed."
      >
        {brokerConnected ? (
          <p className="text-sm text-primary">Connected ✓</p>
        ) : (
          <form action={connectUpstox}>
            <Button type="submit" disabled={!disclosureAccepted}>
              Connect Upstox
            </Button>
            {!disclosureAccepted && (
              <p className="mt-2 text-xs text-muted-foreground">
                Accept the risk disclosure first.
              </p>
            )}
          </form>
        )}
      </Step>
    </div>
  );
}

function Step({
  n,
  done,
  title,
  desc,
  children,
}: {
  n: number;
  done: boolean;
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="font-mono text-xs text-primary">
          Step {n} {done ? "· done" : ""}
        </CardDescription>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{desc}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function NotConfigured() {
  return (
    <div className="mx-auto max-w-md py-10">
      <Card>
        <CardHeader>
          <CardTitle>Setup pending</CardTitle>
          <CardDescription>
            Configure Supabase (and Upstox API keys) to run onboarding.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Add the keys from <code className="text-foreground">.env.example</code> to{" "}
          <code className="text-foreground">apps/web/.env.local</code> and{" "}
          <code className="text-foreground">apps/engine/.env</code>.
        </CardContent>
      </Card>
    </div>
  );
}
