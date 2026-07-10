"""Speech-to-text for AuraOS voice mode."""

from dataclasses import dataclass
from math import exp
from pathlib import Path


@dataclass(frozen=True)
class TranscriptionResult:
    """Transcribed text with an estimated confidence."""

    text: str
    confidence: float


class SpeechToText:
    """Transcribe recorded audio with faster-whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None

    def transcribe(self, audio_path: Path) -> str:
        return self.transcribe_with_confidence(audio_path).text

    def transcribe_with_confidence(self, audio_path: Path) -> TranscriptionResult:
        model = self._get_model()
        segments, _ = model.transcribe(
            str(audio_path),
            beam_size=5,
            language=self.language,
            vad_filter=True,
            condition_on_previous_text=False,
            no_speech_threshold=0.65,
            log_prob_threshold=-0.8,
            compression_ratio_threshold=2.4,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 250},
        )
        segment_list = list(segments)
        text = " ".join(segment.text.strip() for segment in segment_list).strip()
        if not text or not segment_list:
            return TranscriptionResult("", 0.0)

        confidences = []
        for segment in segment_list:
            avg_logprob = getattr(segment, "avg_logprob", -1.0)
            no_speech_prob = getattr(segment, "no_speech_prob", 0.0)
            confidence = max(0.0, min(1.0, exp(avg_logprob) * (1.0 - no_speech_prob)))
            confidences.append(confidence)

        return TranscriptionResult(text, sum(confidences) / len(confidences))

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as error:
            raise RuntimeError("Missing dependency: install faster-whisper for speech-to-text.") from error

        self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model
