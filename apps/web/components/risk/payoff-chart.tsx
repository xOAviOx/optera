"use client";

/**
 * Payoff diagram (pure SVG, no chart lib). Draws the at-expiry P&L curve with
 * shaded profit/loss zones, the current (T+0) mark-to-model curve, breakevens,
 * and a spot marker. Colors come from the theme's --profit / --loss CSS vars.
 */

interface PayoffChartProps {
  spots: number[];
  pnlExpiry: number[];
  pnlT0: number[];
  breakevens: number[];
  spot: number;
}

const PROFIT = "hsl(var(--profit))";
const LOSS = "hsl(var(--loss))";

function compactInr(v: number): string {
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(1)}Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(1)}L`;
  if (a >= 1e3) return `${sign}₹${(a / 1e3).toFixed(1)}k`;
  return `${sign}₹${a.toFixed(0)}`;
}

export function PayoffChart({ spots, pnlExpiry, pnlT0, breakevens, spot }: PayoffChartProps) {
  const W = 760;
  const H = 380;
  const m = { top: 18, right: 18, bottom: 36, left: 66 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;

  if (spots.length < 2) {
    return (
      <div className="grid h-64 place-items-center text-sm text-muted-foreground">
        Add a leg to see the payoff.
      </div>
    );
  }

  const xMin = spots[0]!;
  const xMax = spots[spots.length - 1]!;
  const all = [...pnlExpiry, ...pnlT0, 0];
  let yMin = Math.min(...all);
  let yMax = Math.max(...all);
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const padY = (yMax - yMin) * 0.08;
  yMin -= padY;
  yMax += padY;

  const sx = (s: number) => m.left + ((s - xMin) / (xMax - xMin)) * iw;
  const sy = (p: number) => m.top + (1 - (p - yMin) / (yMax - yMin)) * ih;
  const zeroY = sy(0);

  const polyline = (ys: number[]) =>
    spots.map((s, i) => `${sx(s).toFixed(1)},${sy(ys[i] ?? 0).toFixed(1)}`).join(" ");

  // Area between the expiry curve and the zero line, split by clip into +/-.
  const area =
    `M ${sx(xMin).toFixed(1)},${zeroY.toFixed(1)} ` +
    spots.map((s, i) => `L ${sx(s).toFixed(1)},${sy(pnlExpiry[i] ?? 0).toFixed(1)}`).join(" ") +
    ` L ${sx(xMax).toFixed(1)},${zeroY.toFixed(1)} Z`;

  const xTicks = Array.from({ length: 5 }, (_, i) => xMin + (i / 4) * (xMax - xMin));
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + (i / 4) * (yMax - yMin));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Payoff diagram">
      <defs>
        <clipPath id="clip-profit">
          <rect x={m.left} y={m.top} width={iw} height={Math.max(0, zeroY - m.top)} />
        </clipPath>
        <clipPath id="clip-loss">
          <rect x={m.left} y={zeroY} width={iw} height={Math.max(0, m.top + ih - zeroY)} />
        </clipPath>
      </defs>

      {/* gridlines + y labels */}
      {yTicks.map((t, i) => (
        <g key={`y${i}`}>
          <line
            x1={m.left}
            x2={m.left + iw}
            y1={sy(t)}
            y2={sy(t)}
            stroke="hsl(var(--border))"
            strokeWidth={1}
            opacity={0.5}
          />
          <text
            x={m.left - 8}
            y={sy(t) + 3}
            textAnchor="end"
            fontSize={10}
            fill="hsl(var(--muted-foreground))"
          >
            {compactInr(t)}
          </text>
        </g>
      ))}

      {/* x labels */}
      {xTicks.map((t, i) => (
        <text
          key={`x${i}`}
          x={sx(t)}
          y={m.top + ih + 20}
          textAnchor="middle"
          fontSize={10}
          fill="hsl(var(--muted-foreground))"
        >
          {Math.round(t).toLocaleString("en-IN")}
        </text>
      ))}

      {/* shaded P/L zones */}
      <path d={area} fill={PROFIT} opacity={0.16} clipPath="url(#clip-profit)" />
      <path d={area} fill={LOSS} opacity={0.16} clipPath="url(#clip-loss)" />

      {/* zero line */}
      <line
        x1={m.left}
        x2={m.left + iw}
        y1={zeroY}
        y2={zeroY}
        stroke="hsl(var(--muted-foreground))"
        strokeWidth={1.25}
      />

      {/* breakevens */}
      {breakevens
        .filter((b) => b >= xMin && b <= xMax)
        .map((b, i) => (
          <g key={`be${i}`}>
            <line
              x1={sx(b)}
              x2={sx(b)}
              y1={m.top}
              y2={m.top + ih}
              stroke="hsl(var(--muted-foreground))"
              strokeWidth={1}
              strokeDasharray="2 3"
              opacity={0.7}
            />
            <text
              x={sx(b)}
              y={m.top + ih + 20}
              textAnchor="middle"
              fontSize={9}
              fill="hsl(var(--muted-foreground))"
            >
              BE {Math.round(b).toLocaleString("en-IN")}
            </text>
          </g>
        ))}

      {/* spot marker */}
      <line
        x1={sx(spot)}
        x2={sx(spot)}
        y1={m.top}
        y2={m.top + ih}
        stroke="hsl(var(--primary))"
        strokeWidth={1.25}
        strokeDasharray="4 3"
      />
      <text x={sx(spot)} y={m.top + 2} textAnchor="middle" fontSize={9} fill="hsl(var(--primary))">
        spot {Math.round(spot).toLocaleString("en-IN")}
      </text>

      {/* T+0 curve (dashed, muted) */}
      <polyline
        points={polyline(pnlT0)}
        fill="none"
        stroke="hsl(var(--muted-foreground))"
        strokeWidth={1.5}
        strokeDasharray="5 4"
      />

      {/* expiry curve (solid, prominent) */}
      <polyline
        points={polyline(pnlExpiry)}
        fill="none"
        stroke="hsl(var(--foreground))"
        strokeWidth={2}
      />
    </svg>
  );
}
