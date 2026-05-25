from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return (project_root() / os.getenv("DEMO1_DATA_DIR", "data")).resolve()


def trace_path() -> Path:
    return (project_root() / os.getenv("DEMO1_TRACE_PATH", "trace.jsonl")).resolve()
