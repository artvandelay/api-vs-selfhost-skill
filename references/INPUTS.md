# Input contract

Fields accepted by `scripts/calc.py`. All `gpu.*` fields are nested under one
`gpu` object. Units are SI / decimal — no commas or suffixes in JSON values.
Engine rejects null / non-numeric / non-positive values with exit 2 and a
self-describing `{"error", "field"}` JSON.

## `python3 scripts/calc.py inference`

| field | type | unit | required | notes |
| --- | --- | --- | --- | --- |
| `params_b` | float | billions | yes | total resident params — drives VRAM. For MoE, pass the full size (all experts load). |
| `total_params_b` | float | billions | no | MoE total; VRAM is sized on `max(params_b, total_params_b)` |
| `active_params_b` | float | billions | no | MoE active; validated `<= total` but does **not** change inference VRAM or cost |
| `quant` | string | `fp16` / `int8` / `int4` | yes | lowercase |
| `queries_per_week` | int | requests/wk | yes | |
| `api_cost_per_query_usd` | float | USD | yes | the full blended per-query API cost (input+output token rates). Cost enters here — token counts are **not** a separate input. |
| `traffic_pattern` | string | enum | yes | `uniform` / `business` / `business_hours` / `bursty` / `always_warm` / `cold_per_query` |
| `hot_hours_per_week` | int | hrs/wk | only if `cold_per_query` | |
| `replicas` | float | GPUs | no | GPUs needed to serve the volume; default 1. Self-host cost scales linearly with this. |
| `gpu.name` | string | label | no | from `GPU_SPECS.md` (label only) |
| `gpu.vram_gb` | float | GB | yes | from `GPU_SPECS.md` |
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
