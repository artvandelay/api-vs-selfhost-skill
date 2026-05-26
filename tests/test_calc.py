#!/usr/bin/env python3
"""Smoke tests for calc.py. Stdlib only — no pytest required.

Run from repo root:
    python3 -m unittest discover tests/
"""
import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CALC = REPO_ROOT / "scripts" / "calc.py"


def run(subcmd, payload):
    """Run calc.py <subcmd> with JSON payload on stdin. Return (returncode, json_or_str)."""
    proc = subprocess.run(
        ["python3", str(CALC), subcmd],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, proc.stdout


class TestInference(unittest.TestCase):
    def test_70b_int4_h100_selfhost_wins(self):
        rc, r = run("inference", {
            "params_b": 70, "active_params_b": 70, "quant": "int4",
            "queries_per_week": 1_000_000, "avg_tokens_per_query": 800,
            "api_cost_per_query_usd": 0.002, "traffic_pattern": "business",
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989},
        })
        self.assertEqual(rc, 0)
        self.assertTrue(r["fits"])
        self.assertAlmostEqual(r["vram_needed_gb"], 42.0, places=4)
        self.assertEqual(r["verdict"], "selfhost_wins")

    def test_405b_fp16_infeasible(self):
        rc, r = run("inference", {
            "params_b": 405, "active_params_b": 405, "quant": "fp16",
            "queries_per_week": 1_000_000, "avg_tokens_per_query": 800,
            "api_cost_per_query_usd": 0.002, "traffic_pattern": "business",
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989},
        })
        self.assertEqual(rc, 0)
        self.assertFalse(r["fits"])
        self.assertEqual(r["verdict"], "infeasible")

    def test_tiny_volume_api_wins(self):
        rc, r = run("inference", {
            "params_b": 70, "active_params_b": 70, "quant": "int4",
            "queries_per_week": 1000, "avg_tokens_per_query": 800,
            "api_cost_per_query_usd": 0.002, "traffic_pattern": "business",
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989},
        })
        self.assertEqual(rc, 0)
        self.assertEqual(r["verdict"], "api_wins")


class TestFinetune(unittest.TestCase):
    def test_guanaco_65b_qlora_anchor(self):
        """Anchor from ASSUMPTIONS.md §1: ~4.7h on H100. Engine should land in [3.0, 8.0]."""
        rc, r = run("finetune", {
            "active_params_b": 65, "total_params_b": 65, "method": "qlora",
            "num_examples": 10000, "tokens_per_example": 500, "epochs": 3,
            "experiments_multiplier": 1.0, "prep_cost_usd": 0,
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989, "gpus_per_node": 8},
        })
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(r["single_gpu_hours"], 3.0)
        self.assertLessEqual(r["single_gpu_hours"], 8.0)

    def test_moe_active_drives_compute(self):
        """Qwen3-235B-A22B: 22B active, 235B total. Compute scales with active."""
        rc, r = run("finetune", {
            "active_params_b": 22, "total_params_b": 235, "method": "qlora",
            "num_examples": 100000, "tokens_per_example": 1000, "epochs": 3,
            "experiments_multiplier": 2.5, "prep_cost_usd": 0,
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989, "gpus_per_node": 8},
        })
        self.assertEqual(rc, 0)
        self.assertEqual(r["cluster_topology"], "multi-gpu")


class TestErrorPaths(unittest.TestCase):
    def test_bad_subcommand(self):
        rc, r = run("bogus", {})
        self.assertEqual(rc, 2)
        self.assertIn("unknown subcommand", r["error"])

    def test_missing_field(self):
        rc, r = run("inference", {"params_b": 70})
        self.assertEqual(rc, 2)
        self.assertIn("missing field", r["error"])

    def test_unknown_quant(self):
        rc, r = run("inference", {
            "params_b": 70, "active_params_b": 70, "quant": "fp8",
            "queries_per_week": 1, "avg_tokens_per_query": 1,
            "api_cost_per_query_usd": 0, "traffic_pattern": "business",
            "gpu": {"vram_gb": 80, "usd_per_hr": 1},
        })
        self.assertEqual(rc, 2)
        self.assertIn("unknown quant", r["error"])


if __name__ == "__main__":
    unittest.main()
