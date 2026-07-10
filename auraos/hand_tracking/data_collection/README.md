# AuraOS Hand Gesture Dataset Recorder

This tool records labeled MediaPipe hand landmarks into an append-safe CSV dataset. It is separate from the live AuraOS cursor controller, so recording data cannot trigger mouse clicks, scrolling, voice actions, or system shortcuts.

## Install

From the project root:

```bash
python3 -m pip install -r requirements.txt
```

On macOS, allow your terminal app or Python to use the camera in System Settings > Privacy & Security > Camera.

## Run

```bash
python3 -m auraos.hand_tracking.data_collection.recorder
```

Useful options:

```bash
python3 -m auraos.hand_tracking.data_collection.recorder --sample-interval 0.15 --min-confidence 0.70 --duplicate-distance 0.015
```

## Keyboard Controls

- `1` pointing
- `2` open_palm
- `3` two_fingers
- `4` thumb_index_pinch
- `5` thumb_middle_pinch
- `6` closed_fist
- `7` spread_fingers
- `8` idle
- `R` start recording
- `S` stop recording
- `P` pause or resume while recording
- `D` delete the current recording session from the CSV
- `Q` quit

## Output Files

Raw samples are written to:

```text
dataset/raw/hand_gestures.csv
```

Session metadata is written to:

```text
recordings/session_metadata.json
```

Each run gets a unique `session_id`. The CSV is append-safe: existing samples are preserved unless you press `D` to delete the current session.

## CSV Schema

The columns are:

```text
timestamp, session_id, frame_id, gesture, handedness, confidence, x0, y0, z0, ... x20, y20, z20
```

Coordinates are normalized MediaPipe landmarks. Each row contains one detected hand with 21 landmarks and 63 numeric landmark values.

## Adding a Gesture Class

Edit `GESTURES` in:

```text
auraos/hand_tracking/data_collection/config.py
```

Add the new gesture name to the list, then restart the recorder. If you add more than nine gestures, extend the key handling in `recorder.py` so every class has a clear shortcut.

## Collection Guidance

Aim for at least 500 to 1,000 high-quality samples per gesture before training a first model. More is better when gestures look similar, such as pinch variants.

Collect data across:

- different lighting: bright room, dim room, side light, screen glow
- different angles: palm facing camera, slight rotation, wrist tilt
- different distances: close, mid-distance, farther from webcam
- different users and hand sizes
- both left and right hands
- realistic transitions into and out of each gesture

Use `idle` for natural non-command hand positions so future models learn what not to trigger.
