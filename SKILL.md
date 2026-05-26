---
name: api-vs-selfhost-skill
description: Decide API-vs-self-host LLM economics and fine-tuning ROI from any user context (code, PRDs, traffic logs, billing screenshots). Fetches live GPU prices from Runpod/Lambda/Modal, API prices from models.dev or vendor pages, and quality rank from lmarena.ai, then calls a deterministic local Python script for VRAM, billed-hours, and capex math. Use when the user asks "should I self-host", "API vs self-host", "fine-tune cost", "fine-tuning ROI", "what GPU do I need for <model>", "OpenAI bill too high", or pastes a billing screenshot / PRD comparing closed APIs to open-weight models.
---

# API vs Self-Host

Decide API-vs-self-host LLM economics from whatever context the user gives you.
Fetch live prices, run `scripts/calc.py` for math, write a short report.

## Trigger

- "should I self-host" / "API vs self-host" / "cost to self-host"
- "fine-tune cost" / "fine-tuning ROI"
- "what GPU do I need for \<model\>"
- "OpenAI/Anthropic bill too high" / "is open-source cheaper than \<API\>"
- User pastes a billing screenshot, PRD, or break-even question

Out of scope: pretraining from scratch, image/audio models, non-LLM workloads.

## Workflow

1. **Extract** — read the user's message, open files, and attachments. Map signals (volume, model, spend, traffic shape, quality bar) to fields in [`references/INPUTS.md`](references/INPUTS.md).
2. **Fetch live data** — GPU $/hr from <https://www.runpod.io/pricing> (or Lambda/Modal), API per-token prices from <https://models.dev/> or the vendor page, model quality Elo from <https://lmarena.ai/>. Cite URL + timestamp in the report.
3. **Clarify** — if volume, model, or spend are missing, ask. Don't guess silently. Batch related questions.
4. **Calculate** — `echo '<json>' | python3 scripts/calc.py inference` (or `finetune`). Run more scenarios (different traffic patterns, quants, GPU tiers) when they would change the answer.
5. **Report** — verdict + cost table + assumptions with sources + what would flip the answer.

## Rules

- All VRAM, GPU-hour, and dollar math goes through `scripts/calc.py`. Never compute it in-prompt.
- GPU static specs come from [`references/GPU_SPECS.md`](references/GPU_SPECS.md). Prices come from live fetches.
- Math derivations and constants live in [`references/ASSUMPTIONS.md`](references/ASSUMPTIONS.md) (stub points to the canonical source).
- Show every assumption you made with its source and a confidence note.

## Engine

### Inference

```bash
echo '{"params_b":70,"active_params_b":70,"quant":"int4","queries_per_week":1000000,"avg_tokens_per_query":800,"api_cost_per_query_usd":0.002,"traffic_pattern":"business","gpu":{"name":"H100 80GB","vram_gb":80,"usd_per_hr":2.90,"bf16_tflops":989}}' | python3 scripts/calc.py inference
```

Output keys: `fits`, `infeasible`, `vram_needed_gb`, `selfhost_weekly_usd`, `api_weekly_usd`, `weekly_savings_usd`, `savings_pct`, `verdict` (`selfhost_wins` / `api_wins` / `infeasible`), `warnings`, `derivation`.

### Fine-tune

```bash
echo '{"active_params_b":65,"total_params_b":65,"method":"qlora","num_examples":10000,"tokens_per_example":500,"epochs":3,"experiments_multiplier":1.0,"prep_cost_usd":0,"gpu":{"name":"H100 80GB","vram_gb":80,"usd_per_hr":2.90,"bf16_tflops":989,"gpus_per_node":8}}' | python3 scripts/calc.py finetune
```

Output keys: `single_gpu_hours`, `ft_vram_gb`, `cluster_topology`, `hours_with_cluster`, `gpu_cost_total_usd`, `total_capex_usd`, `warnings`, `derivation`.

Engine errors exit 2 with `{"error": "...", "field": "..."}` — fix the input and retry.

## Notes

- **MoE models**: pass `total_params_b` (drives VRAM) and `active_params_b` (drives FLOPs).
- **`infeasible` verdict**: model exceeds GPU VRAM. Try higher quant, smaller model, or a bigger GPU and re-run.
- **`api_wins` verdict**: say so plainly. Don't contort the analysis to favor self-host.
- **Quality gap**: if the self-host model's Elo is >100 below the API model, flag it in the report — cost isn't everything.

## See also

- Web calculator: <https://artvandelay.github.io/should-i-self-host-llm/>
- Calculator source: <https://github.com/artvandelay/should-i-self-host-llm>
- "Code as Agent Harness": <https://arxiv.org/abs/2605.18747>
