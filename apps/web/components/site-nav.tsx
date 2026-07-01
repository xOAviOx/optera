import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  Briefcase,
  LineChart,
  ScrollText,
  Zap,
} from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

const NAV = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/positions", label: "Positions", icon: Briefcase },
  { href: "/simulator", label: "Simulator", icon: Zap },
  { href: "/risk", label: "Risk", icon: LineChart },
  { href: "/chain", label: "Chain", icon: BarChart3 },
  { href: "/copilot", label: "Co-Pilot", icon: Bot },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/journal", label: "Journal", icon: ScrollText },
];

export async function SiteNav() {
  let email: string | null = null;
  if (isSupabaseConfigured) {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    email = user?.email ?? null;
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground font-bold">
            O
          </span>
          <span className="font-semibold tracking-tight">Optera</span>
          <span className="ml-1 rounded bg-secondary px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
            analytics
          </span>
        </Link>

        <nav className="hidden items-center gap-1 sm:flex">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {email ? (
            <>
              <span className="hidden text-xs text-muted-foreground md:inline">{email}</span>
              <form action="/auth/signout" method="post">
                <button className={buttonVariants({ variant: "ghost", size: "sm" })} type="submit">
                  Sign out
                </button>
              </form>
            </>
          ) : (
            <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
