import { Activity, BarChart3, Bot, LineChart, ScrollText } from "lucide-react";
import Link from "next/link";

const NAV = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/risk", label: "Risk", icon: LineChart },
  { href: "/chain", label: "Chain", icon: BarChart3 },
  { href: "/copilot", label: "Co-Pilot", icon: Bot },
  { href: "/journal", label: "Journal", icon: ScrollText },
];

export function SiteNav() {
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
      </div>
    </header>
  );
}
