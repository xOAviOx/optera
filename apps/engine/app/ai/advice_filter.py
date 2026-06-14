"""Server-side advice filter — a compliance SECURITY BOUNDARY.

Optera is education/analytics ONLY. This screens model OUTPUT for buy/sell/hold
recommendations, price targets, and directional predictions. It is the last line
of defense behind the system prompt: if output trips a rule, the caller discards
it and returns a safe, education-only message instead.

Patterns are anchored to recommendation/prediction phrasing so ordinary teaching
("if NIFTY rises, your call gains delta") does NOT trip the filter.
"""

from __future__ import annotations

import re

# Each pattern targets clear advice/prediction language, not direction words alone.
_RAW_PATTERNS: tuple[str, ...] = (
    # Direct recommendations aimed at the user
    r"\byou\s+(should|must|need to|ought to|better)\s+"
    r"(buy|sell|short|exit|enter|book|hold|add|close|square|avoid|trade)\b",
    r"\b(i|we)\s+(recommend|suggest|advise)\b",
    r"\bmy\s+(recommendation|advice|suggestion|call)\b",
    r"\b(recommended|suggested)\s+(trade|action|position|strategy|entry|exit|stock|option)\b",
    # Imperative trade instructions
    r"\b(buy|sell|short)\s+(now|today|this\s+(call|put|option|strike)|at\s+market)\b",
    r"\bbook\s+(your\s+)?(profit|loss|profits)\b",
    r"\b(stop[\s-]?loss|target\s+price|price\s+target|target\s+of\s+₹?\d)\b",
    # Directional predictions / price targets
    r"\b(will|going\s+to|gonna|expected\s+to|likely\s+to|set\s+to)\s+"
    r"(rise|fall|rally|crash|go\s+up|go\s+down|reach|hit|cross|touch|test)\b",
    r"\bnifty\s+(will|should|is\s+going\s+to|to\s+reach|to\s+hit)\b",
)

_COMPILED: tuple[re.Pattern[str], ...] = tuple(re.compile(p, re.IGNORECASE) for p in _RAW_PATTERNS)

# Shown to the user when output is blocked (Hinglish, on-brand).
SAFE_REPLACEMENT = (
    "Main sirf risk samajhne mein madad karta hoon — kisi trade ka buy/sell ya "
    "market direction call nahi de sakta. Aap mujhse apne structure ke Greeks, "
    "payoff, breakevens, ya 'what-if' scenarios ke baare mein pooch sakte hain. "
    "(Optera education/analytics only hai — investment advice nahi.)"
)


def find_violations(text: str) -> list[str]:
    """Return the snippets that look like advice/prediction (empty == clean)."""
    if not text:
        return []
    return [m.group(0) for pat in _COMPILED if (m := pat.search(text))]


def is_advice(text: str) -> bool:
    return bool(find_violations(text))


def screen(text: str) -> tuple[str, bool]:
    """Return (safe_text, flagged). Flagged output is swapped for SAFE_REPLACEMENT."""
    if find_violations(text):
        return SAFE_REPLACEMENT, True
    return text, False
