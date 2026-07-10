"""Validate and summarize the recorded hand gesture dataset."""

from __future__ import annotations

import argparse

from auraos.hand_tracking.data_collection.config import DEFAULT_DATASET_PATH
from auraos.hand_tracking.model_training.features import filter_dataset, load_dataset, validate_dataframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AuraOS hand gesture dataset quality.")
    parser.add_argument("--dataset-path", default=DEFAULT_DATASET_PATH, help="Path to hand_gestures.csv.")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Confidence threshold for usable rows.")
    args = parser.parse_args()

    df = load_dataset(args.dataset_path)
    errors = validate_dataframe(df)
    filtered = filter_dataset(df, min_confidence=args.min_confidence)

    print(f"Rows: {len(df)}")
    print(f"Usable rows at confidence >= {args.min_confidence:.2f}: {len(filtered)}")
    print(f"Columns: {len(df.columns)}")
    print("\nGesture counts:")
    print(filtered["gesture"].value_counts().sort_index().to_string())
    print("\nHandedness counts:")
    print(filtered["handedness"].value_counts().sort_index().to_string())
    print("\nConfidence:")
    print(filtered["confidence"].describe().to_string())

    duplicate_count = int(filtered.duplicated().sum())
    print(f"\nExact duplicate rows: {duplicate_count}")

    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("\nDataset validation passed.")


if __name__ == "__main__":
    main()
