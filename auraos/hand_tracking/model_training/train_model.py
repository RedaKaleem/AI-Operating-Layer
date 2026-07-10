"""Train the first AuraOS hand gesture classifier from collected landmarks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from auraos.hand_tracking.data_collection.config import DEFAULT_DATASET_PATH, GESTURES
from auraos.hand_tracking.model_training.features import build_features, filter_dataset, load_dataset, validate_dataframe

DEFAULT_MODEL_DIR = Path("models") / "hand_gesture"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an AuraOS hand gesture landmark classifier.")
    parser.add_argument("--dataset-path", default=DEFAULT_DATASET_PATH, help="Path to hand_gestures.csv.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR, help="Directory to save model artifacts.")
    parser.add_argument("--min-confidence", type=float, default=0.70, help="Minimum confidence row filter.")
    parser.add_argument("--test-size", type=float, default=0.20, help="Held-out test split size.")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducible training.")
    parser.add_argument("--target-accuracy", type=float, default=0.90, help="Accuracy target to report against.")
    args = parser.parse_args()

    df = load_dataset(args.dataset_path)
    errors = validate_dataframe(df)
    if errors:
        for error in errors:
            print(f"Validation error: {error}")
        raise SystemExit(1)

    filtered = filter_dataset(df, min_confidence=args.min_confidence)
    missing = [gesture for gesture in GESTURES if gesture not in set(filtered["gesture"])]
    if missing:
        raise SystemExit(f"Missing gesture classes after filtering: {', '.join(missing)}")

    features, labels = build_features(filtered)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=labels,
    )

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                ExtraTreesClassifier(
                    n_estimators=500,
                    class_weight="balanced",
                    random_state=args.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = float(accuracy_score(y_test, predictions))
    report = classification_report(y_test, predictions, labels=GESTURES, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, predictions, labels=GESTURES).tolist()

    args.model_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.model_dir / "gesture_model.joblib"
    metrics_path = args.model_dir / "metrics.json"
    labels_path = args.model_dir / "labels.json"

    joblib.dump(model, model_path)
    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(Path(args.dataset_path).expanduser()),
        "rows_total": int(len(df)),
        "rows_used": int(len(filtered)),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "min_confidence": args.min_confidence,
        "test_size": args.test_size,
        "random_state": args.random_state,
        "accuracy": accuracy,
        "target_accuracy": args.target_accuracy,
        "classification_report": report,
        "confusion_matrix_labels": GESTURES,
        "confusion_matrix": matrix,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    labels_path.write_text(json.dumps(GESTURES, indent=2) + "\n", encoding="utf-8")

    print(f"Rows used: {len(filtered)} / {len(df)}")
    print(f"Train rows: {len(x_train)}")
    print(f"Test rows: {len(x_test)}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Target: {args.target_accuracy:.2%}")
    print(f"Model: {model_path}")
    print(f"Metrics: {metrics_path}")
    if accuracy < args.target_accuracy:
        print("Warning: accuracy is below target. Collect more varied samples before wiring this into live control.")


if __name__ == "__main__":
    main()
