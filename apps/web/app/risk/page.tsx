import { ComingSoon } from "@/components/coming-soon";

export default function RiskPage() {
  return (
    <ComingSoon
      module="M5"
      title="Risk"
      blurb="Visualize how your book behaves across price and time — payoff curves, Greeks, and stress scenarios."
      features={[
        "Payoff diagram (expiry + T+0) with shaded profit/loss zones, breakevens and max P/L markers",
        "Portfolio Greeks panel with plain-language captions (theta helping vs costing you)",
        "“If NIFTY moves ___%” slider → instant ₹ readout and new Greeks",
        "Scenario simulator: spot move, IV change, days elapsed, with presets (gap up/down, IV crush, expiry, black-swan)",
      ]}
    />
  );
}
