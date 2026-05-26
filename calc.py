#!/usr/bin/env python3
"""Deterministic math for the PH-FT agent skill.

Two subcommands: `inference` and `finetune`. Each reads a JSON object from
stdin and writes a JSON object to stdout. Pure arithmetic only — no network,
no file I/O beyond stdin/stdout, stdlib only. The LLM is responsible for
fetching live pricing/quality data and passing it in as numbers.

Exit codes: 0 on success, 2 on bad input (with `{"error": "..."}` on stdout),
1 on internal error.
"""

import json
import sys

FLOPS_PER_TOKEN_PER_PARAM = 6
BASELINE_MFU = 0.30

FT_METHODS = {
    "full":  {"compute_mult": 1.0,  "mfu_penalty": 1.0,  "bytes_per_param": 14},
    "lora":  {"compute_mult": 0.67, "mfu_penalty": 0.85, "bytes_per_param": 1.0},
    "qlora": {"compute_mult": 0.67, "mfu_penalty": 0.70, "bytes_per_param": 0.5},
}

BYTES_PER_PARAM_INFERENCE = {"fp16": 2.0, "int8": 1.0, "int4": 0.5}
VRAM_OVERHEAD_FACTOR = 1.2

TRAFFIC_PATTERN_HOURS = {
    "uniform": 168,
    "business": 50,
    "bursty": 20,
    "always_warm": 168,
}


def _require(d, key):
    if key not in d:
        raise KeyError(key)
    return d[key]


def compute_inference(inp: dict) -> dict:
    params_b = _require(inp, "params_b")
    quant = _require(inp, "quant")
    queries_per_week = _require(inp, "queries_per_week")
    api_cost_per_query_usd = _require(inp, "api_cost_per_query_usd")
    traffic_pattern = _require(inp, "traffic_pattern")
    gpu = _require(inp, "gpu")
    gpu_vram_gb = _require(gpu, "vram_gb")
    gpu_usd_per_hr = _require(gpu, "usd_per_hr")

    if quant not in BYTES_PER_PARAM_INFERENCE:
        raise ValueError(f"unknown quant {quant}")

    bytes_per_param = BYTES_PER_PARAM_INFERENCE[quant]
    vram_needed_gb = params_b * bytes_per_param * VRAM_OVERHEAD_FACTOR
    vram_headroom_gb = gpu_vram_gb - vram_needed_gb
    fits = vram_needed_gb <= gpu_vram_gb

    if traffic_pattern in TRAFFIC_PATTERN_HOURS:
        billed_hours_per_week = TRAFFIC_PATTERN_HOURS[traffic_pattern]
    elif traffic_pattern == "cold_per_query":
        billed_hours_per_week = inp.get("hot_hours_per_week", 0)
    else:
        raise ValueError(f"unknown traffic_pattern {traffic_pattern}")

    selfhost_weekly_usd = billed_hours_per_week * gpu_usd_per_hr
    api_weekly_usd = queries_per_week * api_cost_per_query_usd
    weekly_savings_usd = api_weekly_usd - selfhost_weekly_usd
    savings_pct = (weekly_savings_usd / api_weekly_usd * 100.0) if api_weekly_usd > 0 else 0.0

    if not fits:
        verdict = "infeasible"
    elif selfhost_weekly_usd < api_weekly_usd:
        verdict = "selfhost_wins"
    else:
        verdict = "api_wins"

    derivation = [
        {"step": "vram_needed_gb", "formula": "params_b * bytes_per_param[quant] * 1.2", "value": vram_needed_gb},
        {"step": "billed_hours", "formula": "pattern -> hours/week", "value": billed_hours_per_week},
        {"step": "selfhost_weekly_usd", "formula": "billed_hours * usd_per_hr", "value": selfhost_weekly_usd},
        {"step": "api_weekly_usd", "formula": "queries_per_week * api_cost_per_query_usd", "value": api_weekly_usd},
    ]

    return {
        "fits": fits,
        "vram_needed_gb": round(vram_needed_gb, 4),
        "vram_headroom_gb": round(vram_headroom_gb, 4),
        "billed_hours_per_week": billed_hours_per_week,
        "selfhost_weekly_usd": round(selfhost_weekly_usd, 4),
        "api_weekly_usd": round(api_weekly_usd, 4),
        "weekly_savings_usd": round(weekly_savings_usd, 4),
        "savings_pct": round(savings_pct, 4),
        "verdict": verdict,
        "derivation": derivation,
    }


def compute_finetune(inp: dict) -> dict:
    active_params_b = _require(inp, "active_params_b")
    total_params_b = _require(inp, "total_params_b")
    method = _require(inp, "method")
    num_examples = _require(inp, "num_examples")
    tokens_per_example = _require(inp, "tokens_per_example")
    epochs = _require(inp, "epochs")
    experiments_multiplier_in = _require(inp, "experiments_multiplier")
    prep_cost_usd = _require(inp, "prep_cost_usd")
    gpu = _require(inp, "gpu")
    gpu_vram_gb = _require(gpu, "vram_gb")
    gpu_usd_per_hr = _require(gpu, "usd_per_hr")
    gpu_bf16_tflops = _require(gpu, "bf16_tflops")
    gpus_per_node = gpu.get("gpus_per_node", 8)

    if method not in FT_METHODS:
        raise ValueError(f"unknown method {method}")

    m = FT_METHODS[method]

    total_tokens = num_examples * tokens_per_example * epochs
    full_flops = FLOPS_PER_TOKEN_PER_PARAM * active_params_b * 1e9 * total_tokens
    method_flops = full_flops * m["compute_mult"]

    peak_flops_per_sec = gpu_bf16_tflops * 1e12
    effective_flops_per_sec = peak_flops_per_sec * BASELINE_MFU * m["mfu_penalty"]
    single_gpu_hours = method_flops / effective_flops_per_sec / 3600.0

    ft_vram_gb = total_params_b * m["bytes_per_param"]
    node_vram_gb = gpu_vram_gb * gpus_per_node

    if ft_vram_gb <= gpu_vram_gb:
        cluster_overhead = 1.10
        cluster_topology = "single-gpu"
    elif ft_vram_gb <= node_vram_gb * 1.15:
        cluster_overhead = 1.35
        cluster_topology = "multi-gpu"
    else:
        cluster_overhead = 1.70
        cluster_topology = "multi-node"

    hours_with_cluster = single_gpu_hours * cluster_overhead
    single_run_gpu_cost_usd = hours_with_cluster * gpu_usd_per_hr
    experiments_multiplier = max(1.0, experiments_multiplier_in)
    gpu_cost_total_usd = single_run_gpu_cost_usd * experiments_multiplier
    total_capex_usd = gpu_cost_total_usd + prep_cost_usd

    derivation = [
        {"step": "total_tokens", "formula": "num_examples * tokens_per_example * epochs", "value": total_tokens},
        {"step": "method_flops", "formula": "6 * active_params * total_tokens * method_multiplier", "value": method_flops},
        {"step": "effective_flops_per_sec", "formula": "bf16_tflops * 1e12 * BASELINE_MFU * mfu_penalty", "value": effective_flops_per_sec},
        {"step": "single_gpu_hours", "formula": "method_flops / effective_flops_per_sec / 3600", "value": single_gpu_hours},
        {"step": "ft_vram_gb", "formula": "total_params_b * bytes_per_param[method]", "value": ft_vram_gb},
        {"step": "cluster_overhead", "formula": "topology bucket from ft_vram_gb vs node_vram_gb", "value": cluster_overhead},
        {"step": "hours_with_cluster", "formula": "single_gpu_hours * cluster_overhead", "value": hours_with_cluster},
        {"step": "single_run_gpu_cost_usd", "formula": "hours_with_cluster * usd_per_hr", "value": single_run_gpu_cost_usd},
        {"step": "gpu_cost_total_usd", "formula": "single_run_gpu_cost_usd * experiments_multiplier", "value": gpu_cost_total_usd},
        {"step": "total_capex_usd", "formula": "gpu_cost_total_usd + prep_cost_usd", "value": total_capex_usd},
    ]

    return {
        "total_tokens": total_tokens,
        "method_flops": method_flops,
        "effective_flops_per_sec": effective_flops_per_sec,
        "single_gpu_hours": round(single_gpu_hours, 4),
        "ft_vram_gb": round(ft_vram_gb, 4),
        "cluster_overhead": cluster_overhead,
        "cluster_topology": cluster_topology,
        "hours_with_cluster": round(hours_with_cluster, 4),
        "single_run_gpu_cost_usd": round(single_run_gpu_cost_usd, 4),
        "experiments_multiplier": experiments_multiplier,
        "gpu_cost_total_usd": round(gpu_cost_total_usd, 4),
        "prep_cost_usd": prep_cost_usd,
        "total_capex_usd": round(total_capex_usd, 4),
        "derivation": derivation,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "missing subcommand"}))
        sys.exit(2)
    sub = sys.argv[1]
    if sub not in ("inference", "finetune"):
        print(json.dumps({"error": f"unknown subcommand {sub}"}))
        sys.exit(2)
    try:
        inp = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}))
        sys.exit(2)
    try:
        if sub == "inference":
            result = compute_inference(inp)
        else:
            result = compute_finetune(inp)
    except KeyError as e:
        print(json.dumps({"error": f"missing field {e.args[0]}"}))
        sys.exit(2)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
