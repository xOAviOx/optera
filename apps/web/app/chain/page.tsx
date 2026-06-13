import { ComingSoon } from "@/components/coming-soon";

export default function ChainPage() {
  return (
    <ComingSoon
      module="M6"
      title="Option Chain & IV"
      blurb="Live option chain for your chosen index or stock, with volatility analytics layered on top."
      features={[
        "Live chain: LTP, IV, OI and volume per strike",
        "IV smile / skew chart",
        "IV rank / percentile vs trailing history (computed and stored daily)",
        "PCR and OI-based stats, clearly labelled “informational, not a signal”",
      ]}
    />
  );
}
