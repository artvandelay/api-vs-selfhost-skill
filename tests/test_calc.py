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
        self.assertIn("missing required field", r["error"])
        self.assertIn("hint", r)

    def test_unknown_quant(self):
        rc, r = run("inference", {
            "params_b": 70, "active_params_b": 70, "quant": "fp8",
            "queries_per_week": 1, "avg_tokens_per_query": 1,
            "api_cost_per_query_usd": 0.001, "traffic_pattern": "business",
            "gpu": {"vram_gb": 80, "usd_per_hr": 1},
        })
        self.assertEqual(rc, 2)
        self.assertIn("unknown quant", r["error"])


INFERENCE_BASE = {
    "params_b": 70,
    "active_params_b": 70,
    "quant": "int4",
    "queries_per_week": 1_000_000,
    "avg_tokens_per_query": 800,
    "api_cost_per_query_usd": 0.002,
    "traffic_pattern": "business",
    "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989},
}

FINETUNE_BASE = {
    "active_params_b": 65,
    "total_params_b": 65,
    "method": "qlora",
    "num_examples": 10000,
    "tokens_per_example": 500,
    "epochs": 3,
    "experiments_multiplier": 1.0,
    "prep_cost_usd": 0,
    "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989, "gpus_per_node": 8},
}


class TestHardenedValidation(unittest.TestCase):
    def test_null_queries_per_week_inference(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = None
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertIn("error", r)
        self.assertEqual(r["field"], "queries_per_week")

    def test_negative_queries_per_week_inference(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = -1000
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertIn("error", r)
        self.assertEqual(r["field"], "queries_per_week")

    def test_zero_bf16_tflops_finetune(self):
        payload = dict(FINETUNE_BASE)
        payload["gpu"] = dict(FINETUNE_BASE["gpu"])
        payload["gpu"]["bf16_tflops"] = 0
        rc, r = run("finetune", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "bf16_tflops")

    def test_negative_usd_per_hr_inference(self):
        payload = dict(INFERENCE_BASE)
        payload["gpu"] = dict(INFERENCE_BASE["gpu"])
        payload["gpu"]["usd_per_hr"] = -1
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "usd_per_hr")

    def test_cold_per_query_without_hot_hours(self):
        payload = dict(INFERENCE_BASE)
        payload["traffic_pattern"] = "cold_per_query"
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "hot_hours_per_week")

    def test_invalid_traffic_pattern(self):
        payload = dict(INFERENCE_BASE)
        payload["traffic_pattern"] = "weekends_only"
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "traffic_pattern")

    def test_active_exceeds_total_params(self):
        payload = dict(INFERENCE_BASE)
        payload["active_params_b"] = 100
        payload["params_b"] = 70
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "active_params_b")

    def test_string_for_numeric_field(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = "100k"
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "queries_per_week")

    def test_nan_value(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = None
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "queries_per_week")

    def test_finetune_zero_num_examples(self):
        payload = dict(FINETUNE_BASE)
        payload["num_examples"] = 0
        rc, r = run("finetune", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "num_examples")

    def test_finetune_zero_epochs(self):
        payload = dict(FINETUNE_BASE)
        payload["epochs"] = 0
        rc, r = run("finetune", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "epochs")


class TestInfeasibleOutput(unittest.TestCase):
    def test_infeasible_zeroes_savings(self):
        rc, r = run("inference", {
            "params_b": 405,
            "active_params_b": 405,
            "quant": "fp16",
            "queries_per_week": 1_000_000,
            "avg_tokens_per_query": 800,
            "api_cost_per_query_usd": 0.002,
            "traffic_pattern": "business",
            "gpu": {"name": "H100 80GB", "vram_gb": 80, "usd_per_hr": 2.90, "bf16_tflops": 989},
        })
        self.assertEqual(rc, 0)
        self.assertTrue(r["infeasible"])
        self.assertEqual(r["savings_pct"], 0)
        self.assertEqual(r["weekly_savings_usd"], 0)
        self.assertGreater(len(r["warnings"]), 0)


class TestWarnings(unittest.TestCase):
    def test_experiments_multiplier_clamp(self):
        payload = dict(FINETUNE_BASE)
        payload["experiments_multiplier"] = 0.5
        rc, r = run("finetune", payload)
        self.assertEqual(rc, 0)
        self.assertTrue(any("experiments_multiplier 0.5 clamped to 1.0" in w for w in r["warnings"]))

    def test_no_warnings_on_clean_input(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = 100_000  # below high-volume replicas nudge
        rc, r = run("inference", payload)
        self.assertEqual(rc, 0)
        self.assertEqual(r["warnings"], [])


class TestInputObjectGuard(unittest.TestCase):
    """Non-object JSON must exit 2 cleanly, never leak an exit-1 exception."""

    def test_scalar_int(self):
        rc, r = run("inference", 42)
        self.assertEqual(rc, 2)
        self.assertIn("must be a JSON object", r["error"])
        self.assertIsNone(r["field"])

    def test_json_null(self):
        rc, r = run("inference", None)
        self.assertEqual(rc, 2)
        self.assertIn("must be a JSON object", r["error"])

    def test_scalar_string(self):
        rc, r = run("inference", "hello")
        self.assertEqual(rc, 2)
        self.assertIn("must be a JSON object", r["error"])

    def test_array(self):
        rc, r = run("finetune", [1, 2, 3])
        self.assertEqual(rc, 2)
        self.assertIn("must be a JSON object", r["error"])

    def test_finetune_scalar(self):
        rc, r = run("finetune", 123)
        self.assertEqual(rc, 2)
        self.assertIn("must be a JSON object", r["error"])


class TestErrorHints(unittest.TestCase):
    """Every validation error should carry an actionable hint."""

    def test_missing_field_has_hint(self):
        rc, r = run("inference", {"params_b": 70})
        self.assertEqual(rc, 2)
        self.assertIn("hint", r)

    def test_string_number_has_hint(self):
        payload = dict(INFERENCE_BASE)
        payload["queries_per_week"] = "100k"
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertIn("hint", r)
        self.assertEqual(r["field"], "queries_per_week")


class TestEnumFieldConsistency(unittest.TestCase):
    """quant/method/subcommand errors must name a fixable field, exit 2."""

    def test_unknown_quant_names_field(self):
        payload = dict(INFERENCE_BASE)
        payload["quant"] = "INT4"
        rc, r = run("inference", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "quant")
        self.assertIn("hint", r)

    def test_unknown_method_names_field(self):
        payload = dict(FINETUNE_BASE)
        payload["method"] = "DPO"
        rc, r = run("finetune", payload)
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "method")
        self.assertIn("hint", r)


class TestMoEInferenceVram(unittest.TestCase):
    """Inference VRAM must scale with TOTAL resident params, not active."""

    def test_total_drives_vram(self):
        # Qwen3-235B-A22B int4: total 235B -> ~141GB, must NOT fit on 80GB.
        rc, r = run("inference", {
            "params_b": 22, "total_params_b": 235, "active_params_b": 22,
            "quant": "int4", "queries_per_week": 100,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(r["vram_needed_gb"], 141.0, places=1)
        self.assertFalse(r["fits"])
        self.assertEqual(r["verdict"], "infeasible")

    def test_active_cannot_exceed_total(self):
        rc, r = run("inference", {
            "params_b": 22, "total_params_b": 100, "active_params_b": 150,
            "quant": "int4", "queries_per_week": 100,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "active_params_b")


class TestReplicas(unittest.TestCase):
    def test_replicas_multiply_selfhost_cost(self):
        base = {
            "params_b": 7, "quant": "int4", "queries_per_week": 100,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        }
        rc1, r1 = run("inference", base)
        rc4, r4 = run("inference", dict(base, replicas=4))
        self.assertEqual(rc1, 0)
        self.assertEqual(rc4, 0)
        self.assertAlmostEqual(r4["selfhost_weekly_usd"], r1["selfhost_weekly_usd"] * 4, places=2)
        self.assertEqual(r4["replicas"], 4.0)

    def test_default_replicas_is_one(self):
        rc, r = run("inference", {
            "params_b": 7, "quant": "int4", "queries_per_week": 100,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(r["replicas"], 1.0)

    def test_high_volume_default_replicas_warns(self):
        rc, r = run("inference", {
            "params_b": 7, "quant": "int4", "queries_per_week": 2_000_000,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(rc, 0)
        self.assertTrue(any("replicas=1" in w for w in r["warnings"]))

    def test_explicit_replicas_no_warning(self):
        rc, r = run("inference", {
            "params_b": 7, "quant": "int4", "queries_per_week": 2_000_000,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "replicas": 3, "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(rc, 0)
        self.assertEqual(r["warnings"], [])

    def test_invalid_replicas_rejected(self):
        rc, r = run("inference", {
            "params_b": 7, "quant": "int4", "queries_per_week": 100,
            "api_cost_per_query_usd": 0.01, "traffic_pattern": "uniform",
            "replicas": 0, "gpu": {"vram_gb": 80, "usd_per_hr": 2.9},
        })
        self.assertEqual(rc, 2)
        self.assertEqual(r["field"], "replicas")


if __name__ == "__main__":
    unittest.main()
