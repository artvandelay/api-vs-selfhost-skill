# API vs Self-Host Skill

*Decide API-vs-self-host LLM economics and fine-tuning ROI directly inside Claude Code, Cursor, Codex, or any agent harness with a shell tool.*

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg) ![Skill](https://img.shields.io/badge/Anthropic-Skill-orange) ![Python](https://img.shields.io/badge/python-3.10+-green)

## Install

```bash
# Claude Code: ~/.claude/skills/   |   Cursor: ~/.cursor/skills/   |   anywhere else: just clone
git clone https://github.com/artvandelay/api-vs-selfhost-skill ~/.claude/skills/api-vs-selfhost-skill
```

Update with `git pull` in that directory. Then ask your agent:

> "Our OpenAI bill is killing us. We do ~1M queries/week at ~1.5k tokens each on GPT-5.4. Should we self-host?"

## What you get

The agent reads your code / PRDs / billing screenshots, fetches live GPU and API prices, runs deterministic VRAM and dollar math via `scripts/calc.py`, and writes a short markdown report with cited sources.

| traffic   | quality   | GPU              | $/hr  | fits | self $/wk | API $/wk  | savings | verdict        |
|-----------|-----------|------------------|-------|------|-----------|-----------|---------|----------------|
| business  | 70B INT4  | H100 PCIe 80GB   | $2.89 | yes  | $144.50   | $3,937.50 | 96.3%   | selfhost_wins  |
| business  | 32B INT4  | L40S 48GB        | $0.86 | yes  | $43.00    | $3,937.50 | 98.9%   | selfhost_wins  |
| uniform   | 70B INT4  | H100 PCIe 80GB   | $2.89 | yes  | $485.52   | $3,937.50 | 87.7%   | selfhost_wins  |
| bursty    | 70B INT4  | H100 PCIe 80GB   | $2.89 | yes  | $57.80    | $3,937.50 | 98.5%   | selfhost_wins  |

Full transcript: [examples/openai-bill-too-high.md](examples/openai-bill-too-high.md)

## How it works

1. **Extract** — scan user message, open files, attachments for volume, model, traffic shape.
2. **Fetch** — live GPU prices (Runpod/Lambda/Modal), API prices (models.dev), quality (lmarena.ai).
3. **Clarify** — ask if volume, model, or spend are missing.
4. **Calculate** — `python3 scripts/calc.py inference` or `finetune` with JSON on stdin.
5. **Report** — verdict, cost comparison, assumptions with sources, what would flip the answer.

```mermaid
flowchart LR
  User["User prompt + context"] --> Agent
  Agent["Agent reads SKILL.md"] -->|"WebFetch"| Web["Runpod / models.dev / lmarena"]
  Agent -->|"python3 scripts/calc.py"| Calc["calc.py (stdlib only)"]
  Calc -->|"JSON + derivation"| Agent
  Agent -->|"markdown report"| User
```

The LLM is the flexible front end; `calc.py` is the deterministic substrate that keeps it from hallucinating prices or VRAM math. This is the [Code as Agent Harness](https://arxiv.org/abs/2605.18747) pattern.

## Files

- `SKILL.md` — agent instructions (workflow + rules)
- `scripts/calc.py` — deterministic math (stdlib only)
- `references/GPU_SPECS.md` — static physical specs (VRAM, BF16 TFLOPS)
- `references/INPUTS.md` — input contract
- `references/ASSUMPTIONS.md` — pointer to canonical assumptions in sister repo
- `examples/openai-bill-too-high.md` — sample transcript
- `tests/test_calc.py` — unit tests

## Requirements

Python 3.10+ (stdlib only). An agent harness with shell + web-fetch.

## Contributing

Issues and PRs welcome: GPU vendors, formula calibration, prompt tweaks. Math changes go to the sister repo, [should-i-self-host-llm](https://github.com/artvandelay/should-i-self-host-llm), which also hosts a [web calculator](https://artvandelay.github.io/should-i-self-host-llm/) for manual one-off lookups.

MIT — see [LICENSE](LICENSE).
