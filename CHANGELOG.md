# Changelog

All notable changes to `api-vs-selfhost-skill` are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-27

Initial public release. The skill is feature-complete: a hardened deterministic engine, a minimal SKILL.md, and a clean dev-facing README.

### Added

- **`scripts/calc.py`** — stdlib-only Python engine with two subcommands (`inference`, `finetune`). JSON in / JSON out. Exit codes: `0` success, `2` bad input with `{"error","field"}`, `1` internal error.
- **Strict input validation** — rejects null, NaN, non-numeric, negative, and zero values where invalid. Engine never crashes on user-controllable input.
- **Honest infeasible output** — when VRAM is insufficient, `savings_pct` and `weekly_savings_usd` are `0` and `infeasible: true` is set (no misleading positive savings).
- **`warnings[]` array** on every successful output (e.g. `experiments_multiplier` clamped to 1.0).
- **MoE sanity check** — `active_params_b > total_params_b` rejected.
- **`traffic_pattern` enum validation** — `cold_per_query` requires `hot_hours_per_week`.
- **`SKILL.md`** with workflow (extract → fetch → clarify → calculate → report), engine examples, MoE / infeasible / api_wins notes.
- **`references/INPUTS.md`** — input contract for the engine.
- **`references/GPU_SPECS.md`** — static GPU specs (H100, H200, B200, A100, L40S, L4, MI300X, RTX 4090).
- **`references/ASSUMPTIONS.md`** — pointer to canonical math in the sister repo.
- **`examples/openai-bill-too-high.md`** — full sample agent transcript.
- **Unit tests** (`tests/test_calc.py`) — 22 tests covering happy paths, validation, infeasible output, and warnings. CI on Python 3.10 / 3.11 / 3.12.
- **README** with mermaid flow, install table for Claude Code / Cursor / Codex CLI, usage example, engine docs, "Works with" badge row, credits, and a link to the sister web calculator.
- **GitHub topics** for discovery: `agent-skills`, `claude-skills`, `cursor-skills`, `codex-skill`, `llm-cost-calculator`, `vram-calculator`, `fine-tuning`, `lora`, etc.

### Engine contract

- **Inference output keys:** `fits`, `infeasible`, `vram_needed_gb`, `selfhost_weekly_usd`, `api_weekly_usd`, `weekly_savings_usd`, `savings_pct`, `verdict` (`selfhost_wins` / `api_wins` / `infeasible`), `warnings`, `derivation`.
- **Finetune output keys:** `single_gpu_hours`, `ft_vram_gb`, `cluster_topology`, `hours_with_cluster`, `gpu_cost_total_usd`, `total_capex_usd`, `warnings`, `derivation`.

### Acknowledgements

- [should-i-self-host-llm](https://github.com/artvandelay/should-i-self-host-llm) — canonical math and the [web calculator](https://artvandelay.github.io/should-i-self-host-llm/).
- [models.dev](https://models.dev/) — open LLM API pricing catalog.
- [Chatbot Arena (lmarena.ai)](https://lmarena.ai/) — quality Elo leaderboard.
- [Runpod](https://www.runpod.io/pricing) / [Lambda](https://lambdalabs.com/service/gpu-cloud) / [Modal](https://modal.com/pricing) — live GPU `$/hr` data.
- [Code as Agent Harness](https://arxiv.org/abs/2605.18747) — the design pattern this skill instantiates.

[0.1.0]: https://github.com/artvandelay/api-vs-selfhost-skill/releases/tag/v0.1.0
