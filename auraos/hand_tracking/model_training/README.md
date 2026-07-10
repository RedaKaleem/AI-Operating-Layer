# AuraOS Hand Gesture Model Training

These scripts train and evaluate a model from `dataset/raw/hand_gestures.csv` without replacing the current rule-based live classifier.

## Validate The Dataset

```bash
python3 -m auraos.hand_tracking.model_training.validate_dataset --min-confidence 0.70
```

## Train A Model

```bash
python3 -m auraos.hand_tracking.model_training.train_model --min-confidence 0.70 --target-accuracy 0.90
```

Artifacts are saved to:

```text
models/hand_gesture/
  gesture_model.joblib
  labels.json
  metrics.json
```

## What The Features Include

The trainer uses:

- raw MediaPipe x/y/z landmarks
- wrist-relative normalized landmarks
- pairwise fingertip distances

This keeps the model more stable across distance and hand size than raw coordinates alone.

## Safe Live Preview

Use this before enabling cursor control:

```bash
python3 -m auraos.hand_tracking.model_training.live_preview
```

The preview shows the trained model prediction beside the rule-based classifier result. It does not import or trigger cursor control, clicks, scrolling, voice commands, or system shortcuts.

## Next Integration Step

After the model consistently clears the target accuracy on held-out data, wire `ModelGestureClassifier` into the live hand-tracking path behind a command-line flag. Keep the rule-based classifier available as a fallback.
