import { Disclaimer } from "@optera/ui";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Placeholder for screens whose feature module hasn't shipped yet. */
export function ComingSoon({
  module,
  title,
  blurb,
  features,
}: {
  module: string;
  title: string;
  blurb: string;
  features: string[];
}) {
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">
            {module}
          </span>
        </div>
        <p className="max-w-2xl text-sm text-muted-foreground">{blurb}</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Planned for this screen</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {features.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                {f}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Not built yet — this feature lands in module {module}.
          </p>
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}
