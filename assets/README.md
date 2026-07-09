# Assets

AuraOS hand tracking uses MediaPipe's built-in `mp.solutions.hands` tracker by default.

You can optionally place MediaPipe's `hand_landmarker.task` model in this directory if you want to run the newer MediaPipe Tasks detector:

```bash
assets/hand_landmarker.task
```

Then pass the model location with:

```bash
./run_auraos_hand_tracking.sh --model-path /path/to/hand_landmarker.task
```
