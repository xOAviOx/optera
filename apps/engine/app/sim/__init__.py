"""Paper-trading simulator: a deterministic market + a paper account ledger.

Hypothetical/paper ONLY — no real orders, no advice (see CLAUDE.md). The market
is a pure function of an integer tick, so it needs no background loop and is
identical across reloads/devices; the client owns play/pause/speed by choosing
which tick to render.
"""
