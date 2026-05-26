# Input contract and defaults

This file documents every field accepted by `scripts/calc.py`, with units, sensible defaults, extraction hints for the LLM, and the confidence tag to attach when a value is defaulted rather than user-provided. The skill should never silently default a high-leverage field — ask the user instead, then record the answer here in the report's assumptions table.

## Legend

- **required?** — `yes` means `calc.py` raises `missing field <name>` if absent. `no` means the script applies a built-in default. "only if ..." means conditionally required.
- **sensible default** — what the LLM should propose if the user gave no signal. `(no default — see SKILL.md "Defaults when user defers" for illustrative placeholders)` means do not default; ask one clarifying question instead, or use illustrative placeholders per Phase 7 if the user defers.
- **confidence-when-defaulted** — the tag the LLM must attach in the report's assumptions table whenever it filled this field without explicit user input.
- All `gpu.*` fields are nested under a single `gpu` object in the JSON payload; see the Frozen Interface Contract in the parent plan or the example payloads in `SKILL.md` Phase 4.
- Units are SI / decimal; no commas or unit suffixes inside the JSON values (e.g. `1000000`, not `"1M"`).

## Inference inputs

Fields consumed by `python3 scripts/calc.py inference`. One row per top-level JSON field, plus one row per `gpu.*` sub-field.

| field | type | unit | required? | sensible default | extraction hints | confidence-when-defaulted |
| --- | --- | --- | --- | --- | --- | --- |
| params_b | float | billions of params | yes | (no default — see SKILL.md "Defaults when user defers" for illustrative placeholders) | Look for model name in code, configs, system prompts (e.g. `llama-3.1-70b`, `qwen2.5-32b`). Map name → param count via `knownModels.json` or the model card on Hugging Face. | low if guessed |
| active_params_b | float | billions of active params | no | equal to `params_b` for dense models | For MoE models (Mixtral, Qwen3-MoE, DeepSeek-V3) use the active-experts count from the model card; for dense models reuse `params_b`. | med |
| quant | string | one of `fp16`, `int8`, `int4` | yes | `int4` for >30B, `fp16` for ≤7B | Look for `bnb_4bit`, `gguf` quant suffix (Q4_K_M → int4, Q8_0 → int8), `--load-in-4bit` flags, vLLM `--quantization` arg. | med |
| queries_per_week | int | requests/week | yes | (no default — see SKILL.md "Defaults when user defers" for illustrative placeholders) | Look in: access logs, billing pages, "<n> requests/day" mentions, Cloudflare/Vercel dashboards screenshots. Multiply daily by 7. | low if guessed |
| avg_tokens_per_query | int | tokens (input+output) | no | 800 | Sum a typical prompt + completion length. Chat apps ≈ 500–1500; RAG ≈ 2000–6000; agents ≈ 4000–20000. | med |
| api_cost_per_query_usd | float | USD per query | yes | (no default — see SKILL.md "Defaults when user defers" for illustrative placeholders) | If only $/1M tokens is known, compute `(input_price * input_tokens + output_price * output_tokens) / 1e6`. Vendor pricing pages or models.dev. | med |
| traffic_pattern | string | one of `uniform`, `business`, `business_hours`, `bursty`, `always_warm`, `cold_per_query` | yes | `business` | `uniform` = 24/7 steady; `business` / `business_hours` = 9–6 weekdays (≈50h/wk); `bursty` = spiky internal tools (~20h/wk); `always_warm` = pinned GPU; `cold_per_query` = serverless cold-starts dominate. | med |
| hot_hours_per_week | int | hours/week | only if `traffic_pattern == "cold_per_query"` | 50 | Override used when traffic shape doesn't match a preset. Estimate from request timestamps. | low |
| cold_start_penalty_sec | int | seconds | no | 30 | Time the GPU stays warm after the last request, on serverless platforms (Modal, Replicate). Vendor docs or measurement. | low |
| gpu.name | string | label | yes | `H100 SXM 80GB` | From `references/GPU_SPECS.md`. Pick the smallest GPU whose VRAM ≥ `vram_needed_gb`. | high |
| gpu.vram_gb | int | gigabytes | yes | from `references/GPU_SPECS.md` | Static per-SKU. Do not scrape. | high |
| gpu.usd_per_hr | float | USD/hr | yes | (none — fetch live) | WebFetch Runpod / Lambda / Modal / Together pricing pages. Cite URL + timestamp. | low if guessed |
| gpu.bf16_tflops | int | TFLOPS | no | from `references/GPU_SPECS.md` | Datasheet peak, no sparsity. Static per-SKU. Not consumed by inference math; used by finetune. | high |

## Fine-tune inputs

Fields consumed by `python3 scripts/calc.py finetune`. Defaults reflect realistic SFT practice (LoRA / QLoRA on instruction data); override aggressively for full fine-tunes or pretraining-style runs.

| field | type | unit | required? | sensible default | extraction hints | confidence-when-defaulted |
| --- | --- | --- | --- | --- | --- | --- |
| active_params_b | float | billions of active params | yes | (no default — see SKILL.md "Defaults when user defers" for illustrative placeholders) | Same as inference. For MoE, only the active experts are trained per token. | low if guessed |
| total_params_b | float | billions of total params | yes | equal to `active_params_b` for dense | For dense models reuse `active_params_b`. For MoE use the full param count (Mixtral 8x7B → 47B). Drives VRAM, not FLOPs. | med |
| method | string | one of `full`, `lora`, `qlora` | yes | `qlora` | Look for `peft`, `LoraConfig`, `bitsandbytes`, `--load-in-4bit`, `unsloth`, `axolotl` configs. Default to `qlora` for >7B if the user didn't say. | med |
| num_examples | int | training rows | yes | (no default — see SKILL.md "Defaults when user defers" for illustrative placeholders) | Count rows in the dataset (`wc -l data.jsonl`), or read the dataset card on Hugging Face. | low if guessed |
| tokens_per_example | int | tokens | yes | 1000 | Average prompt + response length. Instruction tuning ≈ 500–2000; long-context SFT ≈ 4000–16000. | med |
| epochs | int | passes over data | yes | 3 | Standard SFT default. Most papers use 1–5. | med |
| experiments_multiplier | float | runs (incl. failures, sweeps) | no | 2.5 | Real projects do hyperparam sweeps + reruns. 1.0 = single perfect run (rare); 2.5 = realistic; 5+ = research. Values < 1.0 are clamped to 1.0 with a warning. | med |
| prep_cost_usd | float | USD | yes | 0 | Data labeling, synthetic data generation, eval set construction. Often the dominant line item in production FT projects. Ask the user. | low |
| gpu.name | string | label | yes | `H100 SXM 80GB` | Same as inference. | high |
| gpu.vram_gb | int | gigabytes | yes | from `references/GPU_SPECS.md` | Static per-SKU. | high |
| gpu.usd_per_hr | float | USD/hr | yes | (none — fetch live) | Same as inference. | low if guessed |
| gpu.bf16_tflops | int | TFLOPS | yes | from `references/GPU_SPECS.md` | Static per-SKU. | high |
| gpu.gpus_per_node | int | GPUs | no | 8 | Cloud-standard 8-GPU node (HGX H100, DGX). Override only if the user has unusual hardware. Must be > 0 if provided. | high |

## Validation errors

`scripts/calc.py` rejects any required numeric field that is null, non-numeric (string, bool, NaN, inf), or non-positive where positivity is required.

- Reject reason format: `{"error": "...", "field": "<name>"}` on exit 2.
- Common rejections: `queries_per_week <= 0`, `bf16_tflops <= 0`, `num_examples <= 0`, `traffic_pattern` not in enum, `cold_per_query` without `hot_hours_per_week`, `active_params_b > total_params_b`.
- Successful responses include a top-level `warnings` array (empty if none) and inference responses include `infeasible: true|false`. When `infeasible` is true, `savings_pct` and `weekly_savings_usd` are zero.
