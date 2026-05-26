# Example: "Our OpenAI bill is killing us"

A real (simulated) end-to-end session showing the skill answering an
API-vs-self-host question from one user prompt. Vendor prices fetched live
during the session (2026-05-26).

## User

> Hey, our OpenAI bill is killing us. We're on GPT-5.4 for an internal
> support copilot — about 1.5M tokens per query on average (long context,
> lots of retrieved docs), and Slack says we're doing roughly 70k queries
> a day on weekdays, basically nothing on weekends. CFO is asking if we
> should move to Llama or something. Can you tell me if it's worth it?

## Agent (Phase 1: context gathering)

Extracted from the prompt:

| Field | Value | Confidence | Source |
|---|---|---|---|
| API model | GPT-5.4 | high | user message |
| `avg_tokens_per_query` | 1500 (1.5k, not 1.5M — flagging to confirm) | med | user message + sanity |
| `queries_per_week` | 350,000 (70k/day × 5 weekdays) | high | user message |
| `traffic_pattern` | business (weekdays only) | high | user message |
| `params_b` | unspecified | low | — |

## Agent (clarify, max 2 questions per round)

> 1. Did you mean ~1,500 tokens per query (typical RAG) or actually 1.5M?
> 2. Llama 3.1 70B (closest to GPT-5.4, ~100 Elo gap) or 32B (cheaper,
>    ~250 Elo gap)? Quality drop tolerable for an internal tool?

## User

> 1.5k tokens (1k context + 500 generation). 70B but show me 32B too.
> Internal tool, some quality drop is fine.

## Agent (Phase 2: live data fetch)

- `WebFetch https://www.runpod.io/pricing` → H100 PCIe $2.89/hr, L40S $0.86/hr (2026-05-26 15:58Z)
- `WebFetch https://models.dev/` → **HTTP 500**, falling back per SKILL.md failure mode #1
- `WebFetch https://openai.com/api/pricing/` → GPT-5.4: $2.50/M input, $15.00/M output (2026-05-26 15:58Z)
- Blended per-query: 1000 × $2.50/M + 500 × $15.00/M = $0.01125/query

## Agent (Phase 4: engine calls)

```bash
echo '{"params_b":70,"active_params_b":70,"quant":"int4","queries_per_week":350000,"avg_tokens_per_query":1500,"api_cost_per_query_usd":0.01125,"traffic_pattern":"business","gpu":{"name":"H100 PCIe 80GB","vram_gb":80,"usd_per_hr":2.89,"bf16_tflops":989}}' | python3 calc.py inference
```

```json
{"fits": true, "vram_needed_gb": 42.0, "vram_headroom_gb": 38.0,
 "billed_hours_per_week": 50, "selfhost_weekly_usd": 144.5,
 "api_weekly_usd": 3937.5, "weekly_savings_usd": 3793.0,
 "savings_pct": 96.33, "verdict": "selfhost_wins"}
```

## Agent (Phase 5: scenario matrix + sensitivity)

| traffic | quality | GPU | $/hr | fits | self $/wk | API $/wk | savings | verdict |
|---|---|---|---|---|---|---|---|---|
| business | 70B INT4 | H100 PCIe 80GB | $2.89 | yes | $144.50 | $3,937.50 | 96.3% | selfhost_wins |
| business | 32B INT4 | L40S 48GB | $0.86 | yes | $43.00 | $3,937.50 | 98.9% | selfhost_wins |
| uniform 24/7 | 70B INT4 | H100 PCIe 80GB | $2.89 | yes | $485.52 | $3,937.50 | 87.7% | selfhost_wins |
| bursty | 70B INT4 | H100 PCIe 80GB | $2.89 | yes | $57.80 | $3,937.50 | 98.5% | selfhost_wins |

Break-even probe: at 13k queries/wk, API would match self-host weekly cost.
Current volume is 27× above that.

## Agent (Phase 6: headline)

> **Self-host Llama 3.1 70B INT4 on a Runpod H100 PCIe at $2.89/hr during
> business hours — saves ~$3,793/week vs GPT-5.4 at your current volume
> (96% reduction).** Caveats: (1) GPU rental only, add $50-200/wk for
> serving infra; (2) validate quality on real tickets before cutover;
> (3) 32B on an L40S is a $43/wk dogfood option.

## Data sources cited

- GPU pricing: <https://www.runpod.io/pricing> (fetched 2026-05-26T15:58Z)
- API pricing: <https://openai.com/api/pricing> (fetched 2026-05-26T15:58Z, fallback after models.dev 500)
- GPU specs: `references/GPU_SPECS.md` (static)
- Math assumptions: <https://github.com/artvandelay/should-i-self-host-llm/blob/main/src/ft/ASSUMPTIONS.md>
