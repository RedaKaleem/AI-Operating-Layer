#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
python3 auraos/hand_tracking_main.py "$@"
