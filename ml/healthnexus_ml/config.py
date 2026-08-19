"""Paths, versions and shared constants for the ML package."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ML_ROOT = PACKAGE_ROOT.parent
ARTIFACT_DIR = Path(os.getenv("HNX_ARTIFACT_DIR", ML_ROOT / "artifacts"))
DATA_DIR = Path(os.getenv("HNX_DATA_DIR", ML_ROOT / "data"))

# Bumped whenever a retrain changes behaviour. Surfaced to the product API as
# `model_version` so a recommendation can always be traced to the model that
# produced it.
RANKER_VERSION = "ranker-v1"
TRIAGE_VERSION = "triage-v1"
WELLNESS_VERSION = "wellness-v1"

RANK_KINDS = ("doctor", "hospital", "lab", "pharmacy", "insurance")

RANDOM_SEED = 20250819
