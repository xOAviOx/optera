import { cn } from "./lib/cn";

/**
 * Compliance disclaimer reused on EVERY output surface (§5.9). Optera is an
 * education/analytics tool — never investment advice. Do not remove from result views.
 */
export function Disclaimer({
  className,
  variant = "inline",
}: {
  className?: string;
  variant?: "inline" | "footer";
}) {
  const text =
    "Optera sirf risk samajhne aur education ke liye hai — yeh investment ya trading advice nahi hai. Optera SEBI-registered advisor nahi hai.";

  if (variant === "footer") {
    return (
      <p className={cn("text-xs text-muted-foreground leading-relaxed", className)}>{text}</p>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200/90",
        className,
      )}
      role="note"
    >
      {text}
    </div>
  );
}
