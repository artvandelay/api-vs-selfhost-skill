---
name: api-vs-selfhost-skill
description: Decide API-vs-self-host LLM economics and fine-tuning ROI from any user context (code, PRDs, traffic logs, billing screenshots). Fetches live GPU prices from Runpod/Lambda/Modal, API prices from models.dev or vendor pages, and quality rank from lmarena.ai, then calls a deterministic local Python script for VRAM, billed-hours, and capex math. Use when the user asks "should I self-host", "API vs self-host", "fine-tune cost", "fine-tuning ROI", "what GPU do I need for <model>", "OpenAI bill too high", or pastes a billing screenshot / PRD comparing closed APIs to open-weight models.
---

# API vs Self-Host Skill

Decide API-vs-self-host LLM economics and fine-tuning ROI from any context the
user provides — code, PRD, traffic logs, PDFs. Uses live web data for
pricing/quality and a deterministic local script for math.

## When to trigger

Use this skill when the user (or their message) matches any of these intents:

- "should I self-host" / "should we self-host"
- "API vs self-host" / "API or self-host"
- "self-hosting cost" / "cost to self-host"
- "fine-tune cost" / "fine-tuning cost" / "how much to fine-tune"
- "fine-tuning ROI" / "is fine-tuning worth it"
- "what GPU do I need for \<model\>" / "which GPU for Llama 70B"
- "OpenAI bill too high" / "Anthropic spend" / "API bill is killing us"
- "is open-source cheaper" / "cheaper than GPT-4 API"
- User pastes a PRD, architecture doc, or billing screenshot comparing closed
  APIs to open-weight models
- User asks for a break-even analysis on inference volume or a fine-tune capex
  estimate before committing to a GPU cluster

Do **not** trigger for generic ML training cost questions unrelated to LLM
inference or fine-tuning (e.g. pretraining a 7B from scratch, image model
training, non-LLM workloads).

## Hard rules

- **Never compute VRAM, GPU-hours, or dollar costs in your head.** Always call
  `python3 scripts/calc.py` with JSON on stdin and parse JSON from stdout.
- **Never invent GPU prices.** Fetch from vendor pages (Runpod, Lambda, Modal,
  Together, Fireworks, DeepInfra) and cite the URL + fetch timestamp in the
  report.
- **Never invent API per-token prices.** Fetch from https://models.dev/ or the
  vendor's official pricing page. Blend input/output token rates into a
  per-query cost using the user's `avg_tokens_per_query`.
- **Never invent model quality rank.** Fetch from https://lmarena.ai/ (Chatbot
  Arena leaderboard). Compare Elo of the candidate self-host model vs the
  user's current API model.
- **Always show the user every assumption you made**, tagged
  `confidence: high|med|low` in the assumptions table.
- **If the user provided no signal for a required input, ask — do not default
  silently.** Sensible defaults are listed in `references/INPUTS.md`; apply
  them only after the user says "use defaults" or after you ask and they defer.
- **Cap clarifying questions to 2 per round.** Batch related questions; do not
  interrogate across more than two unknowns at once.
- **Do not modify `calc.py` or the web app** during a recommendation session.
- **Cite `references/ASSUMPTIONS.md`** when explaining FLOPs, MFU, cluster
  overhead, or PEFT compute savings — the engine mirrors that document.
- **Use `references/GPU_SPECS.md` for VRAM and BF16 TFLOPS** — do not scrape
  datasheet numbers from the web.

## Phase 1 — Context gathering

Before fetching prices or calling the engine, scan everything the user gave you
and any files you can open in the workspace.

### What to look for

| Signal | Where to find it | Maps to input |
|--------|------------------|---------------|
| Current API spend | Invoices, "$X/month on OpenAI", Stripe exports | Derive `api_cost_per_query_usd` |
| Request volume | Logs, "1M req/week", Cloudflare analytics | `queries_per_week` |
| Tokens per request | Usage dashboards, log sampling, PRD | `avg_tokens_per_query` |
| Model in use | Code (`model="gpt-4o"`), env vars, PRD | API model for quality comparison |
| Target open model | "We want Llama 3.1 70B", HF links | `params_b`, `active_params_b`, `quant` |
| Traffic shape | "Business hours only", "24/7 chatbot" | `traffic_pattern`, `hot_hours_per_week` |
| Fine-tune intent | "SFT on 10k examples", training configs | finetune subcommand fields |
| Quality bar | "Must match GPT-4", "good enough for support bot" | Quality tier for scenario matrix |
| Latency / cold start | "Serverless", "scale to zero" | `traffic_pattern`, `cold_start_penalty_sec` |

### Heuristics

- **Dollar amounts:** Any `$` followed by a number — check if monthly (÷ weeks,
  ÷ queries) or per-query.
- **Request counts:** Look for `/day`, `/week`, `/month`; normalize to
  `queries_per_week`.
- **Model names:** Map known names to param counts via model cards or
  `knownModels.json` in the repo if present. Examples: Llama-3.1-70B → 70B
  dense; Mixtral-8x7B → 47B total / 13B active; Qwen3-235B-A22B → 235B / 22B.
- **Code scan:** Search for `openai`, `anthropic`, `model=`, `vllm`, `ollama`,
  `lora`, `qlora`, `peft`, batch sizes, `max_seq_length`.
- **Attachments:** PDFs, screenshots of billing dashboards, Slack exports —
  OCR or read text for the same signals.
- **PRDs:** Often state traffic, quality bar, and budget in prose; extract
  numbers even when buried in paragraphs.

### Output of Phase 1

Build an internal draft input object per field in `references/INPUTS.md`. Tag
each field `confidence: high|med|low`. Proceed to Phase 2 for any field that
needs live pricing or quality data.

## Phase 2 — Live data fetch

Fetch live data in parallel where possible. Record URL and ISO timestamp for
every fetch.

### GPU prices

WebFetch these URLs (or equivalent vendor pages if one fails):

- https://www.runpod.io/pricing
- https://lambdalabs.com/service/gpu-cloud
- https://modal.com/pricing
- https://www.together.ai/pricing (managed-FT comparison only — not primary
  inference GPU source)

Extract rows of the shape `{name, vram_gb, usd_per_hr}`. Prefer on-demand /
community cloud rates over reserved / enterprise quotes unless the user
specified reserved capacity.

**Selection logic:**

1. From Phase 1, estimate VRAM need: `params_b × bytes_per_param[quant] × 1.2`
   (overhead factor from ASSUMPTIONS.md / engine).
2. Filter vendor rows where `vram_gb >= vram_needed_gb`.
3. Pick the cheapest `usd_per_hr` among eligible rows.
4. Attach `bf16_tflops` from `references/GPU_SPECS.md` by matching GPU family
   (H100, A100, L40S, etc.).

Example extracted row:

```json
{
  "name": "H100 80GB",
  "vram_gb": 80,
  "usd_per_hr": 2.90,
  "bf16_tflops": 989
}
```

### API prices

WebFetch https://models.dev/ or the vendor's official pricing page for the
user's current API model.

Extract `$/input-token` and `$/output-token` (often quoted per 1M tokens).
Blend to per-query cost:

```
input_tokens  = avg_tokens_per_query × 0.4   (adjust if user gave split)
output_tokens = avg_tokens_per_query × 0.6
api_cost_per_query_usd =
  (input_tokens / 1e6) × input_per_1m + (output_tokens / 1e6) × output_per_1m
```

If the user already stated a flat `$X per query` or monthly bill ÷ volume, prefer
their number (`confidence: high`) and cross-check against models.dev
(`confidence: med` if within 2×).

### Quality rank

WebFetch https://lmarena.ai/ (Chatbot Arena leaderboard).

Extract the Elo score for:

1. The user's current API model (or closest named match).
2. Each candidate self-host open-weight model under consideration.

**Warning rule:** If the self-host model's Elo is **>100 points below** the API
model's Elo, warn the user explicitly in the report — cost savings may not
justify the quality drop. Still run the math; let numbers and quality both
inform the recommendation.

### GPU specs (static)

Do **not** scrape VRAM or TFLOPS. Use `references/GPU_SPECS.md`:

| name | vram_gb | bf16_tflops | gpus_per_node |
|------|---------|-------------|---------------|
| H100 SXM 80GB | 80 | 989 | 8 |
| H200 SXM | 141 | 989 | 8 |
| B200 | 192 | 2250 | 8 |
| A100 80GB | 80 | 312 | 8 |
| A100 40GB | 40 | 312 | 8 |
| L40S | 48 | 362 | 8 |
| L4 | 24 | 121 | 8 |
| MI300X | 192 | 1307 | 8 |

Merge static specs with live `usd_per_hr` from vendor fetch to build the `gpu`
object passed to `calc.py`.

## Phase 3 — Clarify loop

Pseudocode for the clarification loop:

```
inputs = draft from Phase 1 + Phase 2
HIGH_LEVERAGE = [queries_per_week, api_cost_per_query_usd, params_b, quality_bar]

for field in inputs:
    tag confidence: high | med | low

while any field in HIGH_LEVERAGE has confidence == low:
    pick up to 2 lowest-confidence high-leverage fields
    ask user targeted questions (batch into one message)
    update inputs from answers
    re-tag confidence

if user says "use defaults":
    apply defaults from references/INPUTS.md
    tag those fields confidence: med
    disclose defaults in report assumptions table

if still missing required calc.py fields:
    ask up to 2 more questions OR stop with "insufficient context"

proceed to Phase 4
```

**Examples of good clarifying questions (max 2 per round):**

- "Your PRD mentions 'heavy usage' but no volume — roughly how many queries
  per week?"
- "You're on GPT-4o today — is matching its quality non-negotiable, or is a
  ~100 Elo point drop acceptable for 10× cost savings?"

**Do not ask** about BF16 TFLOPS, cluster overhead constants, or MFU — those
are engine assumptions, not user inputs.

## Phase 4 — Call the engine

Run the deterministic script from the repo root. Never substitute mental math.

### Inference

```bash
echo '<json>' | python3 scripts/calc.py inference
```

Example payload (70B INT4, business traffic, H100):

```bash
echo '{"params_b":70,"active_params_b":70,"quant":"int4","queries_per_week":1000000,"avg_tokens_per_query":800,"api_cost_per_query_usd":0.002,"traffic_pattern":"business","gpu":{"name":"H100 80GB","vram_gb":80,"usd_per_hr":2.90,"bf16_tflops":989}}' | python3 scripts/calc.py inference
```

Expected output keys: `fits`, `vram_needed_gb`, `vram_headroom_gb`,
`billed_hours_per_week`, `selfhost_weekly_usd`, `api_weekly_usd`,
`weekly_savings_usd`, `savings_pct`, `verdict`, `derivation`.

`verdict` values:

- `selfhost_wins` — model fits in VRAM and self-host weekly cost < API weekly cost
- `api_wins` — API is cheaper or tie on cost
- `infeasible` — model does not fit in GPU VRAM at chosen quant

### Fine-tune

```bash
echo '<json>' | python3 scripts/calc.py finetune
```

Example payload (QLoRA on 65B, Guanaco-scale dataset):

```bash
echo '{"active_params_b":65,"total_params_b":65,"method":"qlora","num_examples":10000,"tokens_per_example":500,"epochs":3,"experiments_multiplier":1.0,"prep_cost_usd":0,"gpu":{"name":"H100 80GB","vram_gb":80,"usd_per_hr":2.90,"bf16_tflops":989,"gpus_per_node":8}}' | python3 scripts/calc.py finetune
```

Expected output keys: `total_tokens`, `method_flops`, `effective_flops_per_sec`,
`single_gpu_hours`, `ft_vram_gb`, `cluster_overhead`, `cluster_topology`,
`hours_with_cluster`, `single_run_gpu_cost_usd`, `experiments_multiplier`,
`gpu_cost_total_usd`, `prep_cost_usd`, `total_capex_usd`, `derivation`.

### Parse errors

Exit code 2 → stdout is `{"error": "<msg>"}`. Fix the input (missing field,
unknown method) and retry. Exit code 1 → internal error; report to user.

### Sensitivity sweep (mandatory)

After the base case, always run at least:

1. **Traffic ±50%:** `queries_per_week × 0.5` and `queries_per_week × 1.5`
2. **Quality bar −1 tier:** smaller `params_b` (e.g. 70B → 30B) at same quant,
   or same params at higher quant (fp16 → int4)

Record whether `verdict` flips across the sweep. Include in "What would flip
the answer" section.

## Phase 5 — Scenario matrix

Build a comparison table covering **3 traffic patterns × 2 quality bars = 6**
engine invocations (inference path) unless the user only asked about fine-tuning.

### Traffic patterns (3)

| pattern | meaning |
|---------|---------|
| business | Weekday business-hours load (50 h/week billed) |
| uniform | Steady 24/7 load (168 h/week) |
| bursty | Spiky / batch jobs (20 h/week) |

### Quality bars (2)

| tier | example params | notes |
|------|----------------|-------|
| user target | e.g. 70B INT4 | From Phase 1/3 |
| one tier down | e.g. 30B INT4 or 70B with tighter quant | Smaller or more aggressive quant |

### Matrix template

For each of the 6 cells, call:

```bash
echo '<json with this pattern + params>' | python3 scripts/calc.py inference
```

Present results as a markdown table:

| traffic | quality | fits | selfhost $/wk | API $/wk | savings | verdict |
|---------|---------|------|---------------|----------|---------|---------|
| business | 70B INT4 | yes | 145 | 2000 | 93% | selfhost_wins |
| business | 30B INT4 | yes | … | … | … | … |
| uniform | 70B INT4 | yes | … | … | … | … |
| … | … | … | … | … | … | … |

If the user asked about **fine-tuning only**, replace the matrix with a method
comparison table instead: `full` vs `lora` vs `qlora` on the same dataset, same
GPU.

## Phase 6 — Write the report

Deliver a single markdown document with these sections in order.

### 1. Headline recommendation (1 sentence)

Plain English. Example: "Self-host Llama 3.1 70B INT4 on a Runpod H100 at
$2.90/hr during business hours — saves ~$1,855/week vs GPT-4o at your current
volume."

### 2. Comparison matrix table

The 6-cell table from Phase 5 (or fine-tune method comparison).

### 3. Full derivation

Copy verbatim from each `derivation[]` array returned by `calc.py`. Do not
summarize or recompute. Example row:

```
vram_needed_gb = params_b × bytes_per_param[int4] × 1.2 → 42.0
```

Include both inference and fine-tune derivations if both subcommands were run.

### 4. Assumptions table

| assumption | value | confidence | source |
|------------|-------|------------|--------|
| queries_per_week | 1,000,000 | high | user Slack export |
| gpu.usd_per_hr | 2.90 | high | runpod.io/pricing fetched 2026-05-26 |
| api_cost_per_query | 0.002 | med | models.dev GPT-4o blend |
| … | … | … | … |

### 5. What would flip the answer

Bullet list driven by sensitivity sweep:

- "If volume drops below 200k queries/week, API wins (verdict flips at …)"
- "If H100 spot rises above $4.50/hr, API wins"
- "If you require GPT-4o-level Elo (+100 gap), consider staying on API"

### 6. Data sources (cited URLs + timestamps)

```
- GPU pricing: https://www.runpod.io/pricing (fetched 2026-05-26T14:32Z)
- API pricing: https://models.dev/ (fetched 2026-05-26T14:33Z)
- Quality: https://lmarena.ai/ (fetched 2026-05-26T14:33Z)
- GPU specs: references/GPU_SPECS.md (static)
- Math assumptions: references/ASSUMPTIONS.md (static)
```

## Failure modes

### WebFetch fails on a vendor page

1. Try the next vendor in the list (Runpod → Lambda → Modal).
2. If all fail, ask the user for their current GPU $/hr or a recent invoice.
3. Tag any user-supplied price `confidence: med` and note the fetch failure.
4. Never silently use a remembered price from training data.

### `calc.py` returns `verdict: "api_wins"`

Say so clearly. Do not contort the recommendation to favor self-hosting.
Explain: at the user's volume and traffic shape, API weekly cost is lower (or
equal) and/or the model fits without needing self-host. Suggest levers: higher
quant, smaller model, bursty traffic pattern, or negotiate API volume discount.

### `calc.py` returns `verdict: "infeasible"`

The model exceeds GPU VRAM at the chosen quant. Recommend, in order:

1. Higher quant compression (fp16 → int8 → int4)
2. Smaller model (one quality tier down)
3. Larger GPU (next row in GPU_SPECS.md — e.g. A100 80GB → H100 80GB → H200)
4. Multi-GPU serving (note: inference `calc.py` contract is single-GPU VRAM
   check — flag that multi-GPU serving needs manual sharding estimate)

Re-run the engine after each adjustment until `fits: true` or conclude
self-host is impractical at the user's quality bar.

### User context is too thin

If Phase 1 yields no volume, no model, and no cost signal:

1. Stop before fetching prices or calling the engine.
2. Ask exactly 2 targeted questions, e.g.:
   - "What model are you on today, and roughly what do you pay per month?"
   - "About how many requests per day do you serve?"
3. Do not produce a recommendation with fabricated inputs.

### `calc.py` missing or errors on exit 1

Report the error JSON to the user. Do not fall back to manual calculation.
Suggest verifying `python3 scripts/calc.py` exists and Python ≥ 3.10 is available.

### Quality Elo gap > 100 points

Even when `verdict: selfhost_wins`, lead with the quality warning. Cost is not
the only decision factor. Offer a hybrid routing idea (easy queries to self-host,
hard queries to API) as narrative only — out of scope for the calc engine.

### MoE model confusion

If the user names a MoE model (Mixtral, DeepSeek-V3, Qwen3-MoE):

- Use `total_params_b` for VRAM / `params_b` in inference
- Use `active_params_b` for fine-tune FLOPs
- Cite ASSUMPTIONS.md §1 MoE paragraph in the report

### Conflicting signals

When user-stated bill and models.dev price disagree by >2×, prefer the
user-stated bill for the base case (`confidence: high`) and show models.dev as
a cross-check row in the sensitivity section.

## See also

- Sister web calculator: <https://artvandelay.github.io/should-i-self-host-llm/>
- Calculator source code: <https://github.com/artvandelay/should-i-self-host-llm>
- "Code as Agent Harness" paper this skill is modeled on: <https://arxiv.org/abs/2605.18747>
