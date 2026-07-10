"""Run AuraOS voice and hand tracking modes together."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AuraOS voice and hand tracking together.",
        epilog=(
            "Use `--` to pass extra args to voice mode, or `--hand-args` to pass args to hand tracking. "
            "Example: ./run_auraos_multimodal.sh --no-wake-word --control-cursor --hand-args --no-mirror-cursor"
        ),
    )
    parser.add_argument("--seconds", type=float, default=8.0, help="Maximum seconds to listen per voice command.")
    parser.add_argument("--wake-word", default="aura", help="Wake word required before voice commands.")
    parser.add_argument("--no-wake-word", action="store_true", help="Process voice commands without requiring a wake word.")
    parser.add_argument("--voice-device", type=int, help="Input device index for microphone recording.")
    parser.add_argument("--no-indicator", action="store_true", help="Do not launch the Aura activation indicator.")
    parser.add_argument("--hand-camera", type=int, default=0, help="Camera index for hand tracking.")
    parser.add_argument("--control-cursor", action="store_true", help="Enable gesture cursor control.")
    parser.add_argument(
        "--gesture-voice-control",
        action="store_true",
        help="Start voice only; launch hand tracking when you say 'activate gestures'.",
    )
    parser.add_argument("--no-hand-preview", action="store_true", help="Run hand tracking without preview window.")
    parser.add_argument("--no-hand", action="store_true", help="Run voice only.")
    parser.add_argument("--no-voice", action="store_true", help="Run hand tracking only.")
    parser.add_argument(
        "--hand-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Extra arguments passed directly to auraos.hand_tracking_main.",
    )
    args, voice_extra_args = parser.parse_known_args()

    if args.no_hand and args.no_voice:
        print("Nothing to run: remove either --no-hand or --no-voice.")
        raise SystemExit(1)

    processes: list[subprocess.Popen] = []
    try:
        if not args.no_voice:
            voice_command = _voice_command(args, voice_extra_args)
            print(f"Starting voice: {' '.join(voice_command)}")
            processes.append(subprocess.Popen(voice_command))

        if not args.no_hand and not args.gesture_voice_control:
            hand_command = _hand_command(args)
            print(f"Starting hand tracking: {' '.join(hand_command)}")
            processes.append(subprocess.Popen(hand_command))

        _wait_for_processes(processes)
    except KeyboardInterrupt:
        print("\nStopping AuraOS multimodal mode.")
    finally:
        _terminate_processes(processes)


def _voice_command(args: argparse.Namespace, extra_args: list[str]) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "auraos.voice_main",
        "--seconds",
        str(args.seconds),
        "--wake-word",
        args.wake_word,
    ]
    if args.no_wake_word:
        command.append("--no-wake-word")
    if args.voice_device is not None:
        command.extend(["--device", str(args.voice_device)])
    if not args.no_indicator:
        command.append("--indicator")
    command.extend(extra_args)
    return command


def _hand_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "auraos.hand_tracking_main",
        "--camera",
        str(args.hand_camera),
    ]
    if args.control_cursor:
        command.append("--control-cursor")
    if args.no_hand_preview:
        command.append("--no-preview")
    command.extend(args.hand_args)
    return command


def _wait_for_processes(processes: list[subprocess.Popen]) -> None:
    while processes:
        for process in list(processes):
            return_code = process.poll()
            if return_code is None:
                continue

            processes.remove(process)
            if return_code != 0:
                print(f"Child process exited with code {return_code}. Stopping the other mode.")
                return
        time.sleep(0.25)


def _terminate_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.time() + 4.0
    for process in processes:
        while process.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            process.kill()


if __name__ == "__main__":
    main()
