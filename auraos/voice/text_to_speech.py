"""Offline text-to-speech for AuraOS voice mode."""


class TextToSpeech:
    """Speak feedback using pyttsx3."""

    def __init__(self) -> None:
        try:
            import pyttsx3
        except ModuleNotFoundError as error:
            raise RuntimeError("Missing dependency: install pyttsx3 for voice output.") from error

        self.engine = pyttsx3.init()

    def speak(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()
