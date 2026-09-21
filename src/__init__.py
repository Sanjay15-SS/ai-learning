"""Ledgerline docs assistant - Task Set E, Weeks 6 and 7.

Config shared by every module. The corpus is a fictional payments API with a v2 and
a v3, so that "a v2 endpoint recommended to a v3 user" is a failure that can happen.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
DOCS_DIR = CORPUS / "docs"
RUNS = ROOT / "runs"
TRACES = ROOT / "traces"
LOGS = ROOT / "logs"
EVALS = ROOT / "evals"

API_VERSIONS = ("v2", "v3")
CURRENT_VERSION = "v3"

# Backend: "local" (Qwen2.5-3B on this Mac via MLX, no key) or "anthropic".
# Default is local unless an Anthropic key is set.
BACKEND = os.environ.get("DOCS_BACKEND") or (
    "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "local")

# One model everywhere: app, judge, agent, workflow.
MODEL = os.environ.get("DOCS_MODEL") or (
    "claude-opus-5" if BACKEND == "anthropic" else "mlx-community/Qwen2.5-3B-Instruct-4bit")

# USD per million tokens (input, output). Cache writes bill at 1.25x input,
# cache reads at 0.1x input. A server-side fallback bills at the model that ran.
PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # The local model costs $0 to run. Its cost column is a REFERENCE: its tokens priced
    # at Claude Haiku 4.5 list rates, so agent vs workflow cost stays comparable in $.
    "mlx-community/Qwen2.5-3B-Instruct-4bit": (1.00, 5.00),
}
COST_NOTE = ("" if BACKEND == "anthropic" else
             "cost = reference only: local tokens priced at Claude Haiku 4.5 list rates "
             "($1/$5 per M); actual spend is $0")
