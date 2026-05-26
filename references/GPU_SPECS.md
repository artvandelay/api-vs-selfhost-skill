Static physical specs. Prices are fetched live (see SKILL.md Phase 2).
Do not scrape this — it doesn't change.
Sources: NVIDIA / AMD datasheets, cross-referenced with
src/ft/ASSUMPTIONS.md §3 assumption 8 and 19.

## GPU spec reference

| name | vram_gb | bf16_tflops | gpus_per_node | notes |
| --- | --- | --- | --- | --- |
| H100 SXM 80GB | 80  | 989  | 8 | NVIDIA Hopper, datasheet peak no sparsity |
| H200 SXM      | 141 | 989  | 8 | Same compute as H100, more HBM |
| B200          | 192 | 2250 | 8 | NVIDIA Blackwell |
| A100 80GB     | 80  | 312  | 8 | NVIDIA Ampere |
| A100 40GB     | 40  | 312  | 8 | NVIDIA Ampere |
| L40S          | 48  | 362  | 8 | Ada inference-leaning |
| L4            | 24  | 121  | 8 | Ada, low-power inference |
| MI300X        | 192 | 1307 | 8 | AMD CDNA3 |
