#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
python3 -m auraos.ui.activation_indicator "$@"
