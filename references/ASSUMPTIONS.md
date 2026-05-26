# Assumptions (canonical source elsewhere)

The math assumptions, MFU constants, cluster-overhead curves, FT-method
multipliers, and calibration anchors that `calc.py` implements live in
the sister repo — the web calculator that this skill mirrors:

**Raw text (for WebFetch):**
<https://raw.githubusercontent.com/artvandelay/should-i-self-host-llm/main/src/ft/ASSUMPTIONS.md>

**Human-readable:**
<https://github.com/artvandelay/should-i-self-host-llm/blob/main/src/ft/ASSUMPTIONS.md>

When you need to cite §3 row N, quote a formula, or explain MFU / 6N /
cluster-overhead — `WebFetch` the raw URL above and cite by section and
fetch timestamp. Do not paraphrase from memory.

Why a stub: the calculator repo owns the math; this skill owns the agent
harness. Keeping a single source prevents drift. See the README's
"Why a skill, not a website" section for the full rationale.
