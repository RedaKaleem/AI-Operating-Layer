#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
python3 -m auraos.hand_tracking.model_training.live_preview "$@"
