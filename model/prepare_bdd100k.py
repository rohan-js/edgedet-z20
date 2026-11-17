from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .dataset import convert_bdd_record, grouped_train_validation_split, write_jsonl


def prepare(args: argparse.Namespace) -> None:
    output = Path(args.output)
    train_labels = json.loads(Path(args.train_labels).read_text(encoding="utf-8"))
    test_labels = json.loads(Path(args.final_test_labels).read_text(encoding="utf-8"))
    converted = [convert_bdd_record(record, args.train_images) for record in train_labels]
    if len(converted) != args.train_count + args.validation_count:
        raise ValueError(
            f"expected {args.train_count + args.validation_count} official training records, got {len(converted)}"
        )
    train, validation = grouped_train_validation_split(converted, args.validation_count, args.seed)
    if len(train) != args.train_count:
        raise AssertionError("split did not produce the requested training count")
    final_test = [convert_bdd_record(record, args.final_test_images) for record in test_labels]
    if len(final_test) != args.final_test_count:
        raise ValueError(f"expected {args.final_test_count} official validation records, got {len(final_test)}")
    name_sets = [set(item["name"] for item in split) for split in (train, validation, final_test)]
    if name_sets[0] & name_sets[1] or name_sets[0] & name_sets[2] or name_sets[1] & name_sets[2]:
        raise ValueError("dataset splits contain overlapping image names")
    paths = {
        "train": output / "train.jsonl",
        "validation": output / "validation.jsonl",
        "final_test": output / "final_test.jsonl",
    }
    write_jsonl(train, paths["train"])
    write_jsonl(validation, paths["validation"])
    write_jsonl(final_test, paths["final_test"])
    metadata = {
        "format": "edgedet-bdd100k-v1",
        "seed": args.seed,
        "counts": {"train": len(train), "validation": len(validation), "final_test": len(final_test)},
        "official_validation_reserved_for_final_test": True,
        "manifest_sha256": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()
        },
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert official BDD100K detection labels into EdgeDet manifests")
    parser.add_argument("--train-labels", required=True)
    parser.add_argument("--train-images", required=True)
    parser.add_argument("--final-test-labels", required=True)
    parser.add_argument("--final-test-images", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--train-count", type=int, default=63000)
    parser.add_argument("--validation-count", type=int, default=7000)
    parser.add_argument("--final-test-count", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=2026)
    prepare(parser.parse_args())


if __name__ == "__main__":
    main()
