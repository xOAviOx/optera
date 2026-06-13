import { ComingSoon } from "@/components/coming-soon";

export default function JournalPage() {
  return (
    <ComingSoon
      module="M9"
      title="Trade Journal"
      blurb="Auto-logged closed trades with stats and a descriptive (non-judgmental) AI post-trade review."
      features={[
        "Auto-detect closed positions from snapshot diffs and log them",
        "Stats: win rate, avg win/loss, P&L by underlying/strategy, equity curve",
        "AI post-trade review: “here’s what your risk looked like at peak” — descriptive, not advice",
        "Hypothetical strategy analyzer (paper only): payoff, Greeks, POP, margin estimate",
      ]}
    />
  );
}
