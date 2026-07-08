"""AuraOS voice mode entry point."""

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from auraos.ui.activation_indicator import ActivationStateWriter, IndicatorState
from auraos.voice.microphone import MicrophoneRecorder
from auraos.voice.voice_loop import AuraOSVoiceLoop


def main() -> None:
    """Start AuraOS voice mode."""
    parser = argparse.ArgumentParser(description="Run AuraOS voice mode.")
    parser.add_argument("--seconds", type=float, default=8.0, help="Maximum seconds to listen per command.")
    parser.add_argument("--once", action="store_true", help="Listen once, then exit.")
    parser.add_argument("--simulate-text", help="Process typed text through the voice pipeline without recording.")
    parser.add_argument("--test-wake-text", help="Check whether text would activate the wake word.")
    parser.add_argument("--list-audio-devices", action="store_true", help="Show available audio devices, then exit.")
    parser.add_argument("--device", type=int, help="Input device index to use for microphone recording.")
    parser.add_argument("--silence-threshold", type=float, default=0.025, help="Minimum voice activity threshold.")
    parser.add_argument("--silence-seconds", type=float, default=1.2, help="Seconds of silence before recording stops.")
    parser.add_argument("--no-noise-calibration", action="store_true", help="Disable automatic room-noise calibration.")
    parser.add_argument("--noise-multiplier", type=float, default=3.0, help="Noise floor multiplier for speech detection.")
    parser.add_argument("--speech-start-chunks", type=int, default=3, help="Consecutive loud chunks required to start recording.")
    parser.add_argument("--min-record-seconds", type=float, default=0.45, help="Minimum accepted recording length.")
    parser.add_argument("--debug-audio", action="store_true", help="Print microphone volume and threshold diagnostics.")
    parser.add_argument("--wake-word", default="aura", help="Wake word required before voice commands.")
    parser.add_argument("--no-wake-word", action="store_true", help="Process voice commands without requiring a wake word.")
    parser.add_argument("--idle-timeout", type=float, default=10.0, help="Seconds of silence before voice mode exits after waking.")
    parser.add_argument("--indicator", action="store_true", help="Launch the glowy activation indicator UI.")
    parser.add_argument(
        "--indicator-solid-background",
        action="store_true",
        help="Launch the indicator with a dark square background instead of transparency.",
    )
    args = parser.parse_args()

    indicator_process = None
    try:
        indicator = ActivationStateWriter()
        indicator.set_state(IndicatorState.IDLE)
        if args.indicator:
            indicator_command = [sys.executable, "-m", "auraos.ui.activation_indicator"]
            if args.indicator_solid_background:
                indicator_command.append("--solid-background")

            indicator_process = subprocess.Popen(indicator_command)

        recorder = MicrophoneRecorder(
            device=args.device,
            silence_threshold=args.silence_threshold,
            silence_seconds=args.silence_seconds,
            calibrate_noise=not args.no_noise_calibration,
            noise_multiplier=args.noise_multiplier,
            speech_start_chunks=args.speech_start_chunks,
            min_record_seconds=args.min_record_seconds,
            debug_audio=args.debug_audio,
        )
        voice_loop = AuraOSVoiceLoop(
            recorder=recorder,
            wake_word=args.wake_word,
            require_wake_word=not args.no_wake_word,
            idle_timeout_seconds=args.idle_timeout,
            indicator=indicator,
        )
        if args.list_audio_devices:
            print(voice_loop.list_audio_devices())
        elif args.test_wake_text:
            print(f"would_wake={voice_loop.would_wake(args.test_wake_text)}")
        elif args.simulate_text:
            voice_loop.process_text(args.simulate_text)
        elif args.once:
            voice_loop.run_once(args.seconds)
        else:
            voice_loop.run(args.seconds)
    except RuntimeError as error:
        print(error)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        print("\nAuraOS voice mode stopped.")
    finally:
        if indicator_process is not None:
            indicator_process.terminate()


if __name__ == "__main__":
    main()
