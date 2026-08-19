"""Load and save trained artefacts.

Artefacts are joblib bundles under ``ml/artifacts``. The service loads them once
at startup and holds them in memory; nothing here touches the product database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from healthnexus_ml.config import ARTIFACT_DIR


def artifact_path(name: str) -> Path:
    return ARTIFACT_DIR / f"{name}.joblib"


def save(name: str, obj: Any) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = artifact_path(name)
    joblib.dump(obj, path, compress=3)
    return path


def load(name: str) -> Any:
    path = artifact_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f"Model artefact {path} is missing. Run `python -m healthnexus_ml.train` first."
        )
    return joblib.load(path)


def exists(name: str) -> bool:
    return artifact_path(name).exists()
