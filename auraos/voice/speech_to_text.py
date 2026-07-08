"""Speech-to-text for AuraOS voice mode."""

from pathlib import Path


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
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as error:
            raise RuntimeError("Missing dependency: install faster-whisper for speech-to-text.") from error

        self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model
