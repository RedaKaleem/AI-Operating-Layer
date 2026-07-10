"""Voice command loop for AuraOS."""

import subprocess
import sys
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from time import sleep
from time import monotonic

from auraos.hand_tracking import control as gesture_control
from auraos.main import AuraOSCore
from auraos.ui.activation_indicator import ActivationStateWriter, IndicatorState
from auraos.voice.microphone import MicrophoneRecorder
from auraos.voice.speech_to_text import SpeechToText
from auraos.voice.text_to_speech import TextToSpeech


VOICE_SLEEP_COMMANDS = {
    "cancel",
    "go to sleep",
    "sleep",
    "stop",
    "stop listening",
    "that is all",
    "that's all",
    "goodbye",
}

VOICE_EXIT_COMMANDS = {
    "close aura",
    "exit program",
    "quit program",
    "quit voice mode",
    "shut down",
    "shutdown",
    "shutdown aura",
}

REPEAT_COMMANDS = {
    "repeat",
    "repeat that",
    "repeat last response",
    "say that again",
}

START_DICTATION_COMMANDS = {
    "type it",
    "type this",
    "type that",
    "typing mode",
    "start typing",
    "start dictation",
    "dictation",
    "start dictating",
}

STOP_DICTATION_COMMANDS = {
    "stop typing",
    "stop dictation",
    "done typing",
    "finish typing",
}

ACTIVATE_GESTURE_COMMANDS = {
    "activate gestures",
    "activate gesture",
    "activate hand tracking",
    "start gestures",
    "start gesture",
    "start hand tracking",
    "turn on gestures",
    "turn on hand tracking",
    "enable gestures",
    "enable hand tracking",
}

DEACTIVATE_GESTURE_COMMANDS = {
    "deactivate gestures",
    "deactivate gesture",
    "deactivate hand tracking",
    "stop gestures",
    "stop gesture",
    "stop hand tracking",
    "turn off gestures",
    "turn off hand tracking",
    "disable gestures",
    "disable hand tracking",
}

WAKE_PREFIXES = {
    "hey",
    "hi",
    "hello",
    "okay",
    "ok",
}

WAKE_ALIASES = {
    "aura",
    "aurora",
    "ora",
}


class VoiceState(Enum):
    """Visible state for voice mode."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    SLEEPING = "sleeping"


class AuraOSVoiceLoop:
    """Record speech, transcribe it, process it, and speak feedback."""

    def __init__(
        self,
        core: AuraOSCore | None = None,
        recorder: MicrophoneRecorder | None = None,
        speech_to_text: SpeechToText | None = None,
        text_to_speech: TextToSpeech | None = None,
        wake_word: str = "aura",
        require_wake_word: bool = True,
        idle_timeout_seconds: float = 10.0,
        indicator: ActivationStateWriter | None = None,
    ) -> None:
        self.core = core or AuraOSCore()
        self.recorder = recorder or MicrophoneRecorder()
        self.speech_to_text = speech_to_text or SpeechToText()
        self.text_to_speech = text_to_speech or TextToSpeech()
        self.wake_word = self._normalize_voice_command(wake_word)
        self.wake_aliases = {self.wake_word, *WAKE_ALIASES}
        self.require_wake_word = require_wake_word
        self.idle_timeout_seconds = idle_timeout_seconds
        self.awake = not require_wake_word
        self.last_activity_at = monotonic()
        self.state = VoiceState.IDLE
        self.last_response = ""
        self.indicator = indicator
        self.dictation_active = False
        self.hand_tracking_process: subprocess.Popen | None = None
        self._set_indicator_state(IndicatorState.IDLE)

    def process_text(self, command: str) -> bool:
        cleaned_command = self._normalize_voice_command(command)
        if not cleaned_command:
            return self._handle_silence()

        if _matches_command(cleaned_command, STOP_DICTATION_COMMANDS):
            self.dictation_active = False
            feedback = "Stopped typing."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return False

        if _matches_command(cleaned_command, VOICE_EXIT_COMMANDS):
            feedback = "Exiting AuraOS voice mode."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            self._stop_hand_tracking()
            return True

        if _matches_command(cleaned_command, VOICE_SLEEP_COMMANDS):
            self.awake = False
            feedback = "Going to sleep."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            self._set_state(VoiceState.SLEEPING)
            return False

        if self.require_wake_word and not self.awake:
            wake_command = self._extract_command_after_wake_word(cleaned_command)
            if wake_command is None:
                print(f"Heard while sleeping: {cleaned_command}")
                self._set_state(VoiceState.SLEEPING)
                return False

            self.awake = True
            self.last_activity_at = monotonic()
            self._set_indicator_state(IndicatorState.LISTENING)
            if not wake_command:
                feedback = "Yes?"
                print(feedback)
                self._speak_feedback(feedback, remember=False)
                return False

            cleaned_command = wake_command

        cleaned_command = self._strip_wake_word_if_present(cleaned_command)
        self.last_activity_at = monotonic()

        gesture_result = self._handle_gesture_command(cleaned_command)
        if gesture_result is not None:
            return gesture_result

        dictation_result = self._handle_dictation_command(cleaned_command)
        if dictation_result is not None:
            return dictation_result

        if cleaned_command in REPEAT_COMMANDS:
            self._repeat_last_response()
            return False

        print(f"You said: {cleaned_command}")
        self._set_state(VoiceState.PROCESSING)
        sleep(0.18)
        result = self.core.process_command(cleaned_command)
        print(result.message)
        if result.message.startswith("Blocked for safety:"):
            self._speak_feedback(result.message, visual_state=IndicatorState.BLOCKED)
        else:
            self._speak_feedback(result.message)
        return result.should_exit

    def list_audio_devices(self) -> str:
        return self.recorder.list_devices()

    def would_wake(self, command: str) -> bool:
        cleaned_command = self._normalize_voice_command(command)
        return self._extract_command_after_wake_word(cleaned_command) is not None

    def run_once(self, duration_seconds: float = 5.0) -> bool:
        if not self.require_wake_word:
            self.awake = True

        if self.awake:
            self._set_state(VoiceState.LISTENING)
        else:
            self._set_state(VoiceState.SLEEPING)

        audio_path = self.recorder.record(duration_seconds)

        try:
            if self.awake:
                self._set_state(VoiceState.PROCESSING)
            transcription = self.speech_to_text.transcribe_with_confidence(audio_path)
            command = transcription.text
            if command:
                print(f"Heard: {command} [voice accuracy: {transcription.confidence:.0%}]")
        finally:
            self._remove_audio_file(audio_path)

        return self.process_text(command)

    def run(self, duration_seconds: float = 5.0) -> None:
        wake_hint = f" Say '{self.wake_word}' once to wake me." if self.require_wake_word else ""
        print(f"AuraOS voice mode is running. Press Ctrl+C to stop.{wake_hint}")
        if self.require_wake_word:
            self._set_state(VoiceState.SLEEPING)

        while True:
            status = "awake" if self.awake else "sleeping"
            print(f"Listening ({status}) for up to {duration_seconds:g} seconds...")
            try:
                should_exit = self.run_once(duration_seconds)
            except RuntimeError as error:
                self._set_state(VoiceState.ERROR)
                print(str(error))
                self._speak_feedback(str(error), remember=False)
                should_exit = True

            if should_exit:
                break

        self._set_state(VoiceState.IDLE)

    def _handle_gesture_command(self, command: str) -> bool | None:
        if _matches_command(command, ACTIVATE_GESTURE_COMMANDS):
            feedback = self._start_hand_tracking()
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return False

        if _matches_command(command, DEACTIVATE_GESTURE_COMMANDS):
            feedback = self._stop_hand_tracking()
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return False

        return None

    def _start_hand_tracking(self) -> str:
        if self.hand_tracking_process is not None and self.hand_tracking_process.poll() is None:
            return "Hand tracking is already active."

        gesture_control.clear_stop_request()
        command = [
            sys.executable,
            "-m",
            "auraos.hand_tracking_main",
            "--control-cursor",
            "--max-hands",
            "2",
        ]
        self.hand_tracking_process = subprocess.Popen(command)
        return "Hand tracking activated."

    def _stop_hand_tracking(self) -> str:
        gesture_control.request_stop("voice")
        if self.hand_tracking_process is None:
            return "Hand tracking deactivated."

        if self.hand_tracking_process.poll() is None:
            self.hand_tracking_process.terminate()
            deadline = monotonic() + 3.0
            while self.hand_tracking_process.poll() is None and monotonic() < deadline:
                sleep(0.05)
            if self.hand_tracking_process.poll() is None:
                self.hand_tracking_process.kill()

        self.hand_tracking_process = None
        return "Hand tracking deactivated."

    def _handle_dictation_command(self, command: str) -> bool | None:
        if _matches_command(command, STOP_DICTATION_COMMANDS):
            self.dictation_active = False
            feedback = "Stopped typing."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return False

        if _matches_command(command, START_DICTATION_COMMANDS):
            self.dictation_active = True
            feedback = "Typing mode on."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return False

        inline_text = self._dictation_text_from_command(command)
        if inline_text is not None:
            self._type_text(inline_text)
            return False

        if self.dictation_active:
            self._type_text(command)
            return False

        return None

    def _dictation_text_from_command(self, command: str) -> str | None:
        prefixes = (
            "type it ",
            "type this ",
            "type that ",
            "type ",
            "write ",
            "write this ",
            "start typing ",
            "start dictation ",
            "start dictating ",
        )
        for prefix in prefixes:
            if command.startswith(prefix):
                return command[len(prefix) :].strip()
        return None

    def _type_text(self, text: str) -> None:
        if not text:
            self.dictation_active = True
            feedback = "Typing mode on."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            return

        self._set_state(VoiceState.PROCESSING)
        try:
            import pyautogui
        except ImportError as error:
            raise RuntimeError("Typing mode requires pyautogui. Install dependencies with `python3 -m pip install -r requirements.txt`.") from error

        pyautogui.write(text, interval=0.01)
        pyautogui.press("space")
        print(f"Typed: {text}")
        self._set_state(VoiceState.IDLE)

    def _normalize_voice_command(self, command: str) -> str:
        cleaned_command = command.strip().lower()
        cleaned_command = cleaned_command.translate(str.maketrans({",": " ", ":": " ", ";": " "}))
        cleaned_command = cleaned_command.rstrip(".!?")
        return " ".join(cleaned_command.split())

    def _extract_command_after_wake_word(self, command: str) -> str | None:
        words = command.split()
        if not words:
            return None

        if words[0] in WAKE_PREFIXES:
            words = words[1:]

        if not words:
            return None

        if words[0] in self.wake_aliases:
            return " ".join(words[1:]).strip()

        return None

    def _strip_wake_word_if_present(self, command: str) -> str:
        wake_command = self._extract_command_after_wake_word(command)
        if wake_command is None:
            return command

        return wake_command or command

    def _handle_silence(self) -> bool:
        if not self.awake:
            return False

        if not self.require_wake_word:
            print("Still listening.")
            return False

        idle_seconds = monotonic() - self.last_activity_at
        if idle_seconds >= self.idle_timeout_seconds:
            self.awake = False
            feedback = "No activity detected. Going to sleep."
            print(feedback)
            self._speak_feedback(feedback, remember=False)
            self._set_state(VoiceState.SLEEPING)
            return False

        print(f"Still listening. Idle for {idle_seconds:.1f} seconds.")
        return False

    def _repeat_last_response(self) -> None:
        if not self.last_response:
            self._speak_feedback("I do not have a previous response yet.", remember=False)
            return

        print(self.last_response)
        self._speak_feedback(self.last_response, remember=False)

    def _speak_feedback(
        self,
        feedback: str,
        remember: bool = True,
        visual_state: IndicatorState = IndicatorState.SPEAKING,
    ) -> None:
        if remember:
            self.last_response = feedback

        self._set_state(VoiceState.SPEAKING, visual_state)
        self.text_to_speech.speak(feedback)
        self._set_state(VoiceState.IDLE)

    def _set_state(self, state: VoiceState, indicator_state: IndicatorState | None = None) -> None:
        if self.state == state:
            if indicator_state is not None:
                self._set_indicator_state(indicator_state)
            return

        self.state = state
        print(f"[voice:{state.value}]")
        if indicator_state is not None:
            self._set_indicator_state(indicator_state)
        elif state == VoiceState.LISTENING:
            self._set_indicator_state(IndicatorState.LISTENING)
        elif state == VoiceState.PROCESSING:
            self._set_indicator_state(IndicatorState.PROCESSING)
        elif state == VoiceState.SPEAKING:
            self._set_indicator_state(IndicatorState.SPEAKING)
        elif state in {VoiceState.IDLE, VoiceState.SLEEPING}:
            self._set_indicator_state(IndicatorState.IDLE)
        elif state == VoiceState.ERROR:
            self._set_indicator_state(IndicatorState.BLOCKED)

    def _set_indicator_state(self, state: IndicatorState) -> None:
        if self.indicator is None:
            return

        hold_seconds = 0.0
        if state == IndicatorState.BLOCKED:
            hold_seconds = 3.0

        self.indicator.set_state(state, hold_seconds=hold_seconds)

    def _remove_audio_file(self, audio_path: Path) -> None:
        try:
            audio_path.unlink()
        except FileNotFoundError:
            pass


def _matches_command(command: str, options: set[str], threshold: float = 0.88) -> bool:
    if command in options:
        return True

    return any(SequenceMatcher(None, command, option).ratio() >= threshold for option in options)
