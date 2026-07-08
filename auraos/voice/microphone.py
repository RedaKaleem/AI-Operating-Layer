"""Microphone recording for AuraOS voice mode."""

import wave
from pathlib import Path
from tempfile import NamedTemporaryFile


class MicrophoneRecorder:
    """Record short microphone clips to WAV files."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: int | None = None,
        silence_threshold: float = 0.025,
        silence_seconds: float = 1.2,
        pre_roll_seconds: float = 0.4,
        calibrate_noise: bool = True,
        calibration_seconds: float = 0.6,
        noise_multiplier: float = 3.0,
        speech_start_chunks: int = 3,
        min_record_seconds: float = 0.45,
        debug_audio: bool = False,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.silence_threshold = silence_threshold
        self.silence_seconds = silence_seconds
        self.pre_roll_seconds = pre_roll_seconds
        self.calibrate_noise = calibrate_noise
        self.calibration_seconds = calibration_seconds
        self.noise_multiplier = noise_multiplier
        self.speech_start_chunks = speech_start_chunks
        self.min_record_seconds = min_record_seconds
        self.debug_audio = debug_audio

    def record(self, duration_seconds: float = 5.0) -> Path:
        """Record until speech ends, capped by duration_seconds."""
        try:
            import sounddevice as sd
            import numpy as np
        except ModuleNotFoundError as error:
            raise RuntimeError("Missing dependency: install sounddevice for microphone input.") from error

        chunk_seconds = 0.1
        chunk_size = int(self.sample_rate * chunk_seconds)
        max_chunks = max(1, int(duration_seconds / chunk_seconds))
        silence_chunks_needed = max(1, int(self.silence_seconds / chunk_seconds))
        pre_roll_chunks = max(1, int(self.pre_roll_seconds / chunk_seconds))
        min_record_chunks = max(1, int(self.min_record_seconds / chunk_seconds))
        chunks = []
        pre_roll = []
        heard_speech = False
        silent_chunks = 0
        loud_chunks = 0
        active_threshold = self.silence_threshold

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
            ) as stream:
                if self.calibrate_noise:
                    active_threshold = self._calibrate_noise_floor(stream, chunk_size, active_threshold)
                    if self.debug_audio:
                        print(f"[audio] threshold={active_threshold:.4f}")

                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_size)
                    volume = float(np.sqrt(np.mean(np.square(chunk.astype("float32") / 32768.0))))
                    if self.debug_audio:
                        print(f"[audio] volume={volume:.4f}")

                    if not heard_speech:
                        pre_roll.append(chunk.copy())
                        pre_roll = pre_roll[-pre_roll_chunks:]

                        if volume >= active_threshold:
                            loud_chunks += 1
                        else:
                            loud_chunks = 0

                        if loud_chunks >= self.speech_start_chunks:
                            heard_speech = True
                            chunks.extend(pre_roll)

                        continue

                    chunks.append(chunk.copy())

                    if volume < active_threshold:
                        silent_chunks += 1
                    else:
                        silent_chunks = 0

                    if len(chunks) >= min_record_chunks and silent_chunks >= silence_chunks_needed:
                        break
        except sd.PortAudioError as error:
            raise RuntimeError(
                "Microphone input is not available. Run with --list-audio-devices, then choose an input device with --device."
            ) from error

        if chunks:
            recording = np.concatenate(chunks)
        else:
            recording = np.zeros((chunk_size, self.channels), dtype="int16")

        audio_file = NamedTemporaryFile(prefix="auraos_voice_", suffix=".wav", delete=False)
        audio_path = Path(audio_file.name)
        audio_file.close()

        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(recording.tobytes())

        return audio_path

    def _calibrate_noise_floor(self, stream, chunk_size: int, fallback_threshold: float) -> float:
        try:
            import numpy as np
        except ModuleNotFoundError:
            return fallback_threshold

        calibration_chunks = max(1, int(self.calibration_seconds / 0.1))
        volumes = []
        for _ in range(calibration_chunks):
            chunk, _ = stream.read(chunk_size)
            volume = float(np.sqrt(np.mean(np.square(chunk.astype("float32") / 32768.0))))
            volumes.append(volume)

        if not volumes:
            return fallback_threshold

        noise_floor = float(np.median(volumes))
        return max(fallback_threshold, noise_floor * self.noise_multiplier)

    def list_devices(self) -> str:
        try:
            import sounddevice as sd
        except ModuleNotFoundError as error:
            raise RuntimeError("Missing dependency: install sounddevice for microphone input.") from error

        devices = str(sd.query_devices()).strip()
        if not devices:
            return "No audio devices found."

        return devices
