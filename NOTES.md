# How this skill was built

This skill was built in a single working session between [Jigar Gosar](https://github.com/artvandelay) and an LLM agent (Claude, running inside Cursor). This document captures the journey honestly — including the parts that didn't work — because most agent-built repos hide the process, and the process here is itself a worked example of the [Code as Agent Harness](https://arxiv.org/abs/2605.18747) pattern the skill is named after.

## The arc

### 1. "Can this website be a skill instead?"

The starting point was a working web calculator ([should-i-self-host-llm](https://github.com/artvandelay/should-i-self-host-llm)) — TypeScript + Vite, manual inputs, instant answer. Jigar's prompt: most users with this question are already inside an agent, so why force them to a website? Could the calculator become a skill the agent invokes from wherever they are?

Three architectures got proposed and rejected before the right one stuck:

| Proposal | Why rejected |
|---|---|
| Portable skill with bundled JS CLI | "Friction for non-JS users" — would force `node`/`npm install` into agent users' repos. |
| Hosted API backend | "Fewest moving pieces" — Jigar didn't want a separate service to manage. |
| **Standalone repo, Python `calc.py` (stdlib only), LLM does live web fetches** | Accepted. |

### 2. Build

Two parallel work streams: port the TypeScript engine math to Python (stdlib only), write `SKILL.md` that tells the LLM how to gather context, fetch live prices, and call the engine. Initial output: `SKILL.md` (~450 lines), `calc.py` (210 lines), references, examples, tests, CI.

### 3. Stress test — 4 subagents

Before declaring done, the skill got hit with four parallel stress-test subagents simulating different user personas and edge cases: numeric edges, adversarial inputs, multi-turn state, harness portability. They found:

- **8 bugs in `calc.py`** — `null` input crashed with `TypeError` instead of clean exit 2; `bf16_tflops=0` divided by zero; negative `queries_per_week` silently accepted and produced nonsense; `infeasible` runs still reported positive savings.
- **15+ gaps in `SKILL.md`** — no trust-boundary, no multi-turn state rules, no sanity bounds, no spot pricing, no anti-sunk-cost clause, …

A plan got written to fix all of it. Three PRs landed:

- **PR1** — `calc.py` hardening: strict validation, honest `infeasible`, `warnings[]` array, `calc.py` → `scripts/calc.py`, +14 unit tests.
- **PR2** — `SKILL.md` hardening: Trust boundary, Phase 7 multi-turn state, Input sanity bounds, 15+ failure-mode subsections.
- **PR3** — doc/data drift: RTX 4090 in `GPU_SPECS.md`, `INPUTS.md` aligned, paths fixed.

`SKILL.md` ballooned from 450 → **569 lines.**

### 4. "Too much flap — trust LLMs to do the right thing"

> "make a plan to redo this in the most elegant simple way possible remove flap trust llms will do the right thing"

This was the most important moment in the session. The stress-test fixes had over-corrected. Every "what if the user does X" had become a 70-line section in `SKILL.md`. We were instructing a capable agent like it was a fragile rules engine.

PR #4 cut `SKILL.md` from **569 → 67 lines.** Deleted:

- Trust boundary, anti-sunk-cost, engine substitution rules
- Phase 7 multi-turn revision tables
- Input sanity bounds
- 15+ failure-mode subsections
- Mandatory 6-cell scenario matrix
- Pseudocode clarify loop

Kept: workflow, three hard rules, one example payload per subcommand, MoE / infeasible / api_wins notes. The engine (`calc.py`) still enforces input validation in code where it belongs. All 22 tests passed unchanged.

The principle: **`calc.py` enforces truth. The LLM handles conversation, clarification, follow-ups, and report formatting.** If something regresses in practice, add one sentence — not a 70-line section.

### 5. README iteration

Five more PRs polished the README in tight loops. Each round was a screenshot or one-line piece of feedback:

- *"the installations instructions are too shabby — just have it different for cursor, claude, codex, give little step by step"* → per-harness collapsible install drawers.
- *"make it nice and clean how typically developers see it"* → ripped the drawers out, single git clone + skills directory table.
- *"move the related webUI version upfront"* → callout under the tagline.
- *"this webui looks ugly it makes it look less prominent"* → callout demoted to a one-liner.
- *"can we put the right tags etc so other repos of awesome skills find this"* → 18 curated GitHub topics.
- *"some good repos have many logos"* (pointing to `K-Dense-AI/scientific-agent-skills`) → Works-with badge row (Claude Code, Cursor, Codex, Gemini CLI, Antigravity).

The README went 145 → 109 → 97 → 109 → 126 → 117 lines as the right balance got found.

### 6. Release

Tagged `v0.1.0`, wrote `CHANGELOG.md`, cut a GitHub release.

## What I (the LLM) learned

A few things that worked, that aren't obvious from the outside:

- **The user pushing back on over-engineering mattered.** When I'd over-corrected during the stress-test pass, the right move was a *prompt that questioned the premise*, not "here's a smaller fix." Plan Mode + "trust LLMs to do the right thing" was the actual unlock.
- **Stress-test-first beat ship-first.** Spawning four adversarial subagents before tagging release surfaced 22+ real issues that no amount of "looks correct to me" would have found.
- **Direct-to-main commits for small tweaks.** Jigar saying *"don't make PR for such small changes just do it"* was correct — opening a PR for a 4-line README tweak adds friction without review value when you're the only committer.
- **Borrowing presentation patterns from kindred repos** ([K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)'s badge row) is faster than designing in a vacuum.

## What didn't make it

- **Windows / non-coder install.** Considered honestly, then dropped — this skill assumes Python + git + a CLI agent, and that's a developer tool. Non-coders use the [web calculator](https://artvandelay.github.io/should-i-self-host-llm/).
- **Pyodide / browser-runnable `calc.py`.** Would unlock claude.ai web-app users (no shell tool). Out of scope for v0.1.0, possibly v0.2.

## Reproducing this

Most of the work happened across these PRs:

- [#1 PR1: calc.py hardening + scripts/ relocation](https://github.com/artvandelay/api-vs-selfhost-skill/pull/1)
- [#2 PR2: SKILL.md hardening](https://github.com/artvandelay/api-vs-selfhost-skill/pull/2)
- [#3 PR3: doc & data drift](https://github.com/artvandelay/api-vs-selfhost-skill/pull/3)
- [#4 Simplify skill: trust the agent, keep the engine](https://github.com/artvandelay/api-vs-selfhost-skill/pull/4) — the one that mattered most
- [#5–#10](https://github.com/artvandelay/api-vs-selfhost-skill/pulls?q=is%3Apr+is%3Aclosed) — README + discoverability

## Acknowledgement

Co-authored by Claude (Anthropic), running in Cursor. Jigar drove the product decisions, the pushbacks, and the taste calls. Claude wrote most of the code, did the stress testing, and got the README into shape.

Built in roughly 8 hours of wall-clock collaboration on May 26–27, 2026.
