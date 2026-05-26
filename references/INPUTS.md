# Input contract

Fields accepted by `scripts/calc.py`. All `gpu.*` fields are nested under one
`gpu` object. Units are SI / decimal — no commas or suffixes in JSON values.
Engine rejects null / non-numeric / non-positive values with exit 2 and a
self-describing `{"error", "field"}` JSON.

## `python3 scripts/calc.py inference`

| field | type | unit | required | notes |
| --- | --- | --- | --- | --- |
| `params_b` | float | billions | yes | total params (for VRAM) |
| `active_params_b` | float | billions | no | for MoE; defaults to `params_b` |
| `quant` | string | `fp16` / `int8` / `int4` | yes | |
| `queries_per_week` | int | requests/wk | yes | |
| `avg_tokens_per_query` | int | tokens | no | input + output combined |
| `api_cost_per_query_usd` | float | USD | yes | blend input+output token rates if only $/1M is known |
| `traffic_pattern` | string | enum | yes | `uniform` / `business` / `business_hours` / `bursty` / `always_warm` / `cold_per_query` |
| `hot_hours_per_week` | int | hrs/wk | only if `cold_per_query` | |
| `gpu.name` | string | label | yes | from `GPU_SPECS.md` |
| `gpu.vram_gb` | int | GB | yes | from `GPU_SPECS.md` |
| `gpu.usd_per_hr` | float | USD/hr | yes | fetch live (Runpod/Lambda/Modal) |
| `gpu.bf16_tflops` | int | TFLOPS | no | from `GPU_SPECS.md`; unused by inference |

## `python3 scripts/calc.py finetune`

| field | type | unit | required | notes |
| --- | --- | --- | --- | --- |
| `active_params_b` | float | billions | yes | drives FLOPs |
| `total_params_b` | float | billions | yes | drives VRAM (= `active_params_b` for dense) |
| `method` | string | `full` / `lora` / `qlora` | yes | |
| `num_examples` | int | rows | yes | |
| `tokens_per_example` | int | tokens | yes | |
| `epochs` | int | passes | yes | |
| `experiments_multiplier` | float | runs | no | default 1.0; values <1.0 clamped with a warning |
| `prep_cost_usd` | float | USD | yes | data labeling / synth data / eval set |
| `gpu.name` | string | label | yes | |
| `gpu.vram_gb` | int | GB | yes | |
| `gpu.usd_per_hr` | float | USD/hr | yes | fetch live |
| `gpu.bf16_tflops` | int | TFLOPS | yes | from `GPU_SPECS.md` |
| `gpu.gpus_per_node` | int | GPUs | no | default 8 |
