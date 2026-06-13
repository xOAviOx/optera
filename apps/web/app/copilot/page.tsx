import { ComingSoon } from "@/components/coming-soon";

export default function CopilotPage() {
  return (
    <ComingSoon
      module="M7"
      title="AI Co-Pilot"
      blurb="A conversational co-pilot that grounds every answer in your real, live book and explains your risk in plain Hinglish — never buy/sell advice."
      features={[
        "Streaming chat in Hinglish / English / Hindi, with persisted sessions",
        "Tool-calling: reads your live positions, Greeks, payoff, scenarios, chain and margin",
        "Intent chips: “Explain my risk simply”, “What if market gaps 2% Monday?”, “Why did my P&L move?”",
        "Hard compliance guardrails — explains risk and mechanics, refuses entry/exit recommendations",
      ]}
    />
  );
}
