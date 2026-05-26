from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from .config import DATASET_URL, data_dir
from .schemas import Problem


def raw_dataset_path() -> Path:
    return data_dir() / "gsmhardv2.jsonl"


def normalized_dataset_path() -> Path:
    return data_dir() / "gsmhardv2_100.jsonl"


def download_dataset(limit: int = 100) -> Path:
    data_dir().mkdir(parents=True, exist_ok=True)
    raw_path = raw_dataset_path()
    with urllib.request.urlopen(DATASET_URL, timeout=60) as response:
        raw_path.write_bytes(response.read())
    records = []
    with raw_path.open("r", encoding="utf-8") as fh:
        for index, line in enumerate(fh):
            if not line.strip():
                continue
            item = json.loads(line)
            if "input" not in item or "target" not in item:
                raise ValueError(f"record {index} missing input/target")
            records.append(
                Problem(
                    id=f"gsmhardv2-{index + 1:04d}",
                    question=str(item["input"]),
                    answer=str(item["target"]),
                    metadata={"original_index": index},
                ).model_dump()
            )
            if len(records) >= limit:
                break
    if len(records) < limit:
        raise ValueError(f"expected {limit} records, got {len(records)}")
    out_path = normalized_dataset_path()
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out_path


def ensure_dataset(limit: int = 100) -> Path:
    path = normalized_dataset_path()
    if not path.exists():
        return download_dataset(limit=max(100, limit))
    return path


def load_problems(limit: int) -> list[Problem]:
    path = ensure_dataset(limit=max(100, limit))
    problems: list[Problem] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                problems.append(Problem.model_validate_json(line))
            if len(problems) >= limit:
                break
    if len(problems) < limit:
        raise ValueError(f"expected {limit} problems, loaded {len(problems)}")
    return problems


def validate_dataset() -> None:
    problems = load_problems(100)
    for problem in problems:
        if not problem.question or not problem.answer:
            raise ValueError(f"invalid problem: {problem.id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download or validate GSM8K-Hard data")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download")
    dl.add_argument("--limit", type=int, default=100)
    sub.add_parser("validate")
    args = parser.parse_args()
    if args.command == "download":
        path = download_dataset(args.limit)
        print(path)
    elif args.command == "validate":
        validate_dataset()
        print("dataset ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
