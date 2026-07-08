"""Glowy activation indicator for AuraOS."""

import argparse
import json
import math
import sys
import time
import tkinter as tk
from enum import Enum
from pathlib import Path


class IndicatorState(Enum):
    """Visual states for the activation indicator."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    BLOCKED = "blocked"


STATE_FILE = Path(__file__).resolve().parent / "activation_state.json"
POSITION_FILE = Path(__file__).resolve().parent / "activation_position.json"
SETTINGS_FILE = Path(__file__).resolve().parent / "activation_settings.json"
TRANSPARENT_COLOR = "#010203"

THEMES = {
    "aurora": {
        "name": "Aurora",
        "accent": "#2bd7ff",
        "accent_2": "#a84cff",
        "idle_outer": "#123d73",
        "idle": "#2bd7ff",
        "listening_outer": "#42106f",
        "listening": "#ba42ff",
        "processing_outer": "#4c0c4b",
        "processing": "#f241d7",
        "speaking_outer": "#103c84",
        "speaking": "#38a6ff",
        "blocked_outer": "#731717",
        "blocked": "#ff3434",
    },
    "violet": {
        "name": "Violet",
        "accent": "#b84cff",
        "accent_2": "#f241d7",
        "idle_outer": "#251354",
        "idle": "#9e6bff",
        "listening_outer": "#3c176d",
        "listening": "#c261ff",
        "processing_outer": "#551550",
        "processing": "#ff52dc",
        "speaking_outer": "#172a75",
        "speaking": "#6a8cff",
        "blocked_outer": "#741818",
        "blocked": "#ff4747",
    },
    "rose": {
        "name": "Rose",
        "accent": "#ff4fc3",
        "accent_2": "#ff8cdd",
        "idle_outer": "#402048",
        "idle": "#ff7dde",
        "listening_outer": "#5a1747",
        "listening": "#ff4fc3",
        "processing_outer": "#632151",
        "processing": "#ff69da",
        "speaking_outer": "#242070",
        "speaking": "#8e7dff",
        "blocked_outer": "#75191f",
        "blocked": "#ff424f",
    },
    "cyan": {
        "name": "Cyan",
        "accent": "#38e0df",
        "accent_2": "#2bd7ff",
        "idle_outer": "#0e3d50",
        "idle": "#42f3f0",
        "listening_outer": "#17446d",
        "listening": "#38a6ff",
        "processing_outer": "#0f4c5a",
        "processing": "#38e0df",
        "speaking_outer": "#123d73",
        "speaking": "#2bd7ff",
        "blocked_outer": "#6b2218",
        "blocked": "#ff6d38",
    },
    "ember": {
        "name": "Ember",
        "accent": "#ffad3d",
        "accent_2": "#ff6d38",
        "idle_outer": "#51330e",
        "idle": "#ffbe4a",
        "listening_outer": "#5a2d13",
        "listening": "#ff8a38",
        "processing_outer": "#603414",
        "processing": "#ffad3d",
        "speaking_outer": "#573513",
        "speaking": "#ffd166",
        "blocked_outer": "#741818",
        "blocked": "#ff3434",
    },
    "frost": {
        "name": "Frost",
        "accent": "#eaf2ff",
        "accent_2": "#9ec9ff",
        "idle_outer": "#243449",
        "idle": "#eaf2ff",
        "listening_outer": "#263b62",
        "listening": "#b7d4ff",
        "processing_outer": "#283058",
        "processing": "#d3c7ff",
        "speaking_outer": "#1c3b62",
        "speaking": "#9ec9ff",
        "blocked_outer": "#5f2020",
        "blocked": "#ff6969",
    },
}


class ActivationStateWriter:
    """Write activation state for the indicator process."""

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.hold_until = 0.0
        self.held_state = ""

    def set_state(self, state: IndicatorState | str, message: str = "", hold_seconds: float = 0.0) -> None:
        state_value = state.value if isinstance(state, IndicatorState) else state
        now = time.time()
        if self.held_state == IndicatorState.BLOCKED.value and now < self.hold_until and state_value in {
            IndicatorState.IDLE.value,
            IndicatorState.SPEAKING.value,
        }:
            return

        self.hold_until = now + hold_seconds
        self.held_state = state_value if hold_seconds > 0 else ""
        payload = {
            "state": state_value,
            "message": message,
            "updated_at": now,
            "hold_until": self.hold_until,
        }
        temp_file = self.state_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(payload), encoding="utf-8")
        temp_file.replace(self.state_file)


class ActivationIndicator:
    """Small always-on-top glowing orb."""

    def __init__(
        self,
        state_file: Path | None = None,
        position_file: Path | None = None,
        settings_file: Path | None = None,
        size: int = 136,
        margin: int = 28,
        demo: bool = False,
        transparent: bool = True,
    ) -> None:
        self.state_file = state_file or STATE_FILE
        self.position_file = position_file or POSITION_FILE
        self.settings_file = settings_file or SETTINGS_FILE
        self.size = size
        self.margin = margin
        self.demo = demo
        self.transparent = transparent
        self.background_color = TRANSPARENT_COLOR if transparent else "#020611"
        self.state = IndicatorState.IDLE
        self.phase = 0.0
        self.last_state_mtime = 0.0
        self.hold_until = 0.0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.window_start_x = 0
        self.window_start_y = 0
        self.last_click_time = 0.0
        self.dashboard: tk.Toplevel | None = None
        self.theme_name = self._load_settings().get("theme", "aurora")
        if self.theme_name not in THEMES:
            self.theme_name = "aurora"
        self.theme = THEMES[self.theme_name]
        self.demo_states = [
            IndicatorState.IDLE,
            IndicatorState.LISTENING,
            IndicatorState.PROCESSING,
            IndicatorState.SPEAKING,
            IndicatorState.BLOCKED,
        ]
        self.demo_started_at = time.time()

        self.root = tk.Tk()
        self.root.title("AuraOS Activation Indicator")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self._configure_transparency()

        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg=self.background_color,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self._place_window()
        self._bind_dragging()

    def run(self) -> None:
        """Start the indicator window."""
        self._tick()
        self.root.mainloop()

    def _place_window(self) -> None:
        saved_position = self._load_position()
        if saved_position is not None:
            x, y = saved_position
        else:
            x, y = self._bottom_right_position()

        x, y = self._clamp_position(x, y)
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def _bottom_right_position(self) -> tuple[int, int]:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - self.size - self.margin
        y = screen_height - self.size - self.margin
        return x, y

    def _bind_dragging(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Double-Button-1>", self._toggle_dashboard)

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.window_start_x = self.root.winfo_x()
        self.window_start_y = self.root.winfo_y()

    def _drag(self, event: tk.Event) -> None:
        delta_x = event.x_root - self.drag_start_x
        delta_y = event.y_root - self.drag_start_y
        x = self.window_start_x + delta_x
        y = self.window_start_y + delta_y
        x, y = self._clamp_position(x, y)
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def _end_drag(self, _event: tk.Event) -> None:
        x, y = self._clamp_position(self.root.winfo_x(), self.root.winfo_y())
        self._save_position(x, y)

    def _toggle_dashboard(self, _event: tk.Event | None = None) -> None:
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self.dashboard.destroy()
            self.dashboard = None
            return

        self._open_dashboard()

    def _open_dashboard(self) -> None:
        self.dashboard = tk.Toplevel(self.root)
        self.dashboard.title("AuraOS")
        self.dashboard.configure(bg="#050912")
        self.dashboard.attributes("-topmost", True)
        self.dashboard.resizable(False, False)
        self.dashboard.protocol("WM_DELETE_WINDOW", self._close_dashboard)
        self._place_dashboard()
        self._build_dashboard()

    def _close_dashboard(self) -> None:
        if self.dashboard is None:
            return

        self.dashboard.destroy()
        self.dashboard = None

    def _place_dashboard(self) -> None:
        if self.dashboard is None:
            return

        width = 760
        height = 560
        orb_x = self.root.winfo_x()
        orb_y = self.root.winfo_y()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = orb_x - width - 18
        y = orb_y - height + self.size

        if x < 16:
            x = orb_x + self.size + 18
        if x + width > screen_width:
            x = max(16, screen_width - width - 16)
        if y < 16:
            y = 16
        if y + height > screen_height:
            y = max(16, screen_height - height - 16)

        self.dashboard.geometry(f"{width}x{height}+{x}+{y}")

    def _build_dashboard(self) -> None:
        if self.dashboard is None:
            return

        for child in self.dashboard.winfo_children():
            child.destroy()

        shell = tk.Frame(self.dashboard, bg="#050912", padx=20, pady=16)
        shell.pack(fill=tk.BOTH, expand=True)

        frame = tk.Frame(shell, bg="#07101f", highlightbackground=self.theme["accent"], highlightthickness=1, padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(frame, bg="#07101f")
        header.pack(fill=tk.X)
        title = tk.Label(
            header,
            text="AURAOS",
            fg=self.theme["accent_2"],
            bg="#07101f",
            font=("Helvetica", 24, "bold"),
        )
        title.pack(side=tk.LEFT)
        subtitle = tk.Label(
            header,
            text="  Activation Indicator",
            fg="#d8e7ff",
            bg="#07101f",
            font=("Helvetica", 23, "bold"),
        )
        subtitle.pack(side=tk.LEFT)
        close_button = tk.Button(
            header,
            text="x",
            command=self._close_dashboard,
            bg="#0b1424",
            fg="#d9e8ff",
            activebackground="#14223a",
            activeforeground="#ffffff",
            bd=0,
            width=3,
        )
        close_button.pack(side=tk.RIGHT)

        status_row = tk.Frame(frame, bg="#07101f")
        status_row.pack(fill=tk.X, pady=(6, 14))
        tk.Label(
            status_row,
            text=f"Current state: {self.state.value.upper()}",
            fg="#8fb6ff",
            bg="#07101f",
            font=("Helvetica", 12),
            anchor="w",
        ).pack(side=tk.LEFT)
        tk.Label(
            status_row,
            text=f"Theme: {self.theme['name']}",
            fg=self.theme["accent"],
            bg="#07101f",
            font=("Helvetica", 12, "bold"),
            anchor="e",
        ).pack(side=tk.RIGHT)

        state_row = tk.Frame(frame, bg="#07101f")
        state_row.pack(fill=tk.X)
        state_cards = [
            ("IDLE", "Dim glow", self.theme["idle"]),
            ("LISTENING", "Bright pulse", self.theme["listening"]),
            ("PROCESSING", "Rotating glow", self.theme["processing"]),
            ("SPEAKING", "Soft wave", self.theme["speaking"]),
            ("BLOCKED", "Red warning", self.theme["blocked"]),
        ]
        for title_text, body_text, color in state_cards:
            self._state_card(state_row, title_text, body_text, color).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        content = tk.Frame(frame, bg="#07101f")
        content.pack(fill=tk.BOTH, expand=True, pady=(18, 0))

        left = tk.Frame(content, bg="#07101f")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        right = tk.Frame(content, bg="#07101f")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self._section_label(left, "Interactions")
        interactions = [
            ("Single click", "Move/drag the orb"),
            ("Double click", "Open or close this panel"),
            ("Sleep", "Say sleep to return to dim idle"),
            ("Shutdown", "Say shutdown to exit voice mode"),
            ("Repeat", "Say repeat to hear the last response"),
        ]
        for label, detail in interactions:
            self._info_row(left, label, detail)

        self._section_label(right, "Customization")
        self._control_panel(right)

        footer = tk.Frame(frame, bg="#0a1426", highlightbackground="#1c355a", highlightthickness=1)
        footer.pack(fill=tk.X, pady=(16, 0))
        footer_text = tk.Label(
            footer,
            text="Flow: wake -> listen -> process -> preview/speak -> idle",
            fg="#cfe4ff",
            bg="#0a1426",
            font=("Helvetica", 12),
            padx=12,
            pady=12,
        )
        footer_text.pack(side=tk.LEFT)
        mini = tk.Canvas(footer, width=120, height=54, bg="#0a1426", highlightthickness=0)
        mini.pack(side=tk.RIGHT, padx=8)
        self._draw_mini_orb(mini, 88, 27)

    def _state_card(self, parent: tk.Frame, title_text: str, body_text: str, color: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#0a1426", highlightbackground="#21466d", highlightthickness=1, padx=8, pady=8)
        tk.Label(card, text=title_text, fg=color, bg="#0a1426", font=("Helvetica", 10, "bold")).pack()
        preview = tk.Canvas(card, width=72, height=54, bg="#0a1426", highlightthickness=0)
        preview.pack(pady=4)
        self._draw_static_orb(preview, 36, 27, color)
        tk.Label(card, text=body_text, fg="#cfe4ff", bg="#0a1426", font=("Helvetica", 10)).pack()
        return card

    def _section_label(self, parent: tk.Frame, text: str) -> None:
        tk.Label(
            parent,
            text=text.upper(),
            fg=self.theme["accent"],
            bg="#07101f",
            font=("Helvetica", 13, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))

    def _info_row(self, parent: tk.Frame, label: str, detail: str) -> None:
        row = tk.Frame(parent, bg="#0a1426", highlightbackground="#193250", highlightthickness=1, padx=12, pady=8)
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=label, fg=self.theme["accent"], bg="#0a1426", font=("Helvetica", 11, "bold"), width=14, anchor="w").pack(
            side=tk.LEFT
        )
        tk.Label(row, text=detail, fg="#d6e5ff", bg="#0a1426", font=("Helvetica", 11), anchor="w").pack(side=tk.LEFT)

    def _control_panel(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg="#0a1426", highlightbackground="#193250", highlightthickness=1, padx=14, pady=12)
        panel.pack(fill=tk.BOTH, expand=True)

        tk.Label(panel, text="Size", fg="#d6e5ff", bg="#0a1426", font=("Helvetica", 11, "bold"), anchor="w").pack(fill=tk.X)
        size_row = tk.Frame(panel, bg="#0a1426")
        size_row.pack(fill=tk.X, pady=(8, 14))
        for size_value in (112, 136, 164):
            button = tk.Button(
                size_row,
                text=str(size_value),
                command=lambda value=size_value: self._resize_indicator(value),
                bg="#0b1424",
                fg=self.theme["accent"],
                activebackground="#14223a",
                activeforeground="#ffffff",
                bd=0,
                width=6,
                pady=4,
            )
            button.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(panel, text="Position", fg="#d6e5ff", bg="#0a1426", font=("Helvetica", 11, "bold"), anchor="w").pack(fill=tk.X)
        position_row = tk.Frame(panel, bg="#0a1426")
        position_row.pack(fill=tk.X, pady=(8, 14))
        positions = [
            ("TL", "top_left"),
            ("TR", "top_right"),
            ("BL", "bottom_left"),
            ("BR", "bottom_right"),
        ]
        for label, position in positions:
            tk.Button(
                position_row,
                text=label,
                command=lambda value=position: self._snap_to_position(value),
                bg="#0b1424",
                fg=self.theme["accent"],
                activebackground="#14223a",
                activeforeground="#ffffff",
                bd=0,
                width=5,
                pady=4,
            ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(panel, text="Theme", fg="#d6e5ff", bg="#0a1426", font=("Helvetica", 11, "bold"), anchor="w").pack(fill=tk.X)
        theme_row = tk.Frame(panel, bg="#0a1426")
        theme_row.pack(fill=tk.X, pady=(8, 0))
        for theme_key, theme in THEMES.items():
            swatch = tk.Canvas(theme_row, width=32, height=32, bg="#0a1426", highlightthickness=0, cursor="hand2")
            outline = "#ffffff" if theme_key == self.theme_name else theme["accent"]
            swatch.create_oval(5, 5, 27, 27, fill=theme["accent"], outline=outline, width=2)
            swatch.create_oval(12, 12, 20, 20, fill=theme["accent_2"], outline="")
            swatch.bind("<Button-1>", lambda _event, key=theme_key: self._set_theme(key))
            swatch.pack(side=tk.LEFT, padx=(0, 8))

    def _resize_indicator(self, size: int) -> None:
        self.size = size
        self.canvas.config(width=self.size, height=self.size)
        x, y = self._clamp_position(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self._save_position(x, y)

    def _snap_to_position(self, position: str) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        positions = {
            "top_left": (self.margin, self.margin),
            "top_right": (screen_width - self.size - self.margin, self.margin),
            "bottom_left": (self.margin, screen_height - self.size - self.margin),
            "bottom_right": (screen_width - self.size - self.margin, screen_height - self.size - self.margin),
        }
        x, y = self._clamp_position(*positions[position])
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self._save_position(x, y)
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self._place_dashboard()

    def _set_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            return

        self.theme_name = theme_name
        self.theme = THEMES[theme_name]
        self._save_settings({"theme": self.theme_name})
        self._draw()
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self._build_dashboard()

    def _draw_static_orb(self, canvas: tk.Canvas, x: int, y: int, color: str) -> None:
        for radius, width in ((24, 2), (17, 2)):
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=width)
        canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="")

    def _draw_mini_orb(self, canvas: tk.Canvas, x: int, y: int) -> None:
        canvas.create_oval(x - 22, y - 22, x + 22, y + 22, outline=self.theme["accent"], width=2)
        canvas.create_oval(x - 30, y - 30, x + 30, y + 30, outline=self.theme["accent_2"], width=2)
        for index, height in enumerate((10, 18, 26, 18, 10)):
            bar_x = x - 10 + index * 5
            color = self.theme["accent"] if index < 2 else self.theme["accent_2"]
            canvas.create_line(bar_x, y - height / 2, bar_x, y + height / 2, fill=color, width=3, capstyle=tk.ROUND)

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        max_x = max(0, screen_width - self.size)
        max_y = max(0, screen_height - self.size)
        return min(max(0, x), max_x), min(max(0, y), max_y)

    def _load_position(self) -> tuple[int, int] | None:
        if not self.position_file.exists():
            return None

        try:
            payload = json.loads(self.position_file.read_text(encoding="utf-8"))
            x = int(payload["x"])
            y = int(payload["y"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

        return x, y

    def _save_position(self, x: int, y: int) -> None:
        payload = {"x": x, "y": y, "updated_at": time.time()}
        temp_file = self.position_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(payload), encoding="utf-8")
        temp_file.replace(self.position_file)

    def _load_settings(self) -> dict[str, str]:
        if not self.settings_file.exists():
            return {}

        try:
            payload = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {key: value for key, value in payload.items() if isinstance(key, str) and isinstance(value, str)}

    def _save_settings(self, settings: dict[str, str]) -> None:
        current_settings = self._load_settings()
        current_settings.update(settings)
        temp_file = self.settings_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(current_settings, indent=2) + "\n", encoding="utf-8")
        temp_file.replace(self.settings_file)

    def _configure_transparency(self) -> None:
        self.root.configure(bg=self.background_color)
        if not self.transparent:
            return

        for attribute_name, value in (
            ("-transparentcolor", self.background_color),
            ("-transparent", True),
        ):
            try:
                self.root.attributes(attribute_name, value)
            except tk.TclError:
                continue

        try:
            self.root.configure(bg="systemTransparent")
            self.background_color = "systemTransparent"
        except tk.TclError:
            self.root.configure(bg=TRANSPARENT_COLOR)
            self.background_color = TRANSPARENT_COLOR

    def _tick(self) -> None:
        self.phase += 0.08
        self._refresh_state()
        self._draw()
        self.root.after(33, self._tick)

    def _refresh_state(self) -> None:
        if self.demo:
            index = int((time.time() - self.demo_started_at) / 2.4) % len(self.demo_states)
            self.state = self.demo_states[index]
            return

        if not self.state_file.exists():
            return

        if time.time() < self.hold_until:
            return

        mtime = self.state_file.stat().st_mtime
        if mtime == self.last_state_mtime:
            return

        self.last_state_mtime = mtime
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.state = IndicatorState(payload.get("state", IndicatorState.IDLE.value))
            self.hold_until = float(payload.get("hold_until", 0.0))
        except (json.JSONDecodeError, ValueError):
            self.state = IndicatorState.IDLE
            self.hold_until = 0.0

    def _draw(self) -> None:
        self.canvas.delete("all")
        center = self.size / 2

        if self.state == IndicatorState.IDLE:
            self._draw_idle(center)
        elif self.state == IndicatorState.LISTENING:
            self._draw_listening(center)
        elif self.state == IndicatorState.PROCESSING:
            self._draw_processing(center)
        elif self.state == IndicatorState.SPEAKING:
            self._draw_speaking(center)
        elif self.state == IndicatorState.BLOCKED:
            self._draw_blocked(center)

    def _draw_idle(self, center: float) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.phase)
        self._glow(center, self.theme["idle_outer"], self.theme["idle"], 34 + pulse * 3, intensity=0.55)
        self._ring(center, 34, self.theme["idle"], 2)
        self._dot(center, self.theme["idle"], 6)

    def _draw_listening(self, center: float) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.phase * 1.8)
        self._glow(center, self.theme["listening_outer"], self.theme["listening"], 37 + pulse * 8, intensity=0.9)
        self._ring(center, 35 + pulse * 4, self.theme["listening"], 3)
        self._draw_waveform(center, self.theme["accent"], self.theme["listening"], scale=1.0 + pulse * 0.4)

    def _draw_processing(self, center: float) -> None:
        self._glow(center, self.theme["processing_outer"], self.theme["processing"], 38, intensity=0.8)
        self._ring(center, 33, self.theme["processing"], 2)
        for offset in (0, 120, 240):
            start = (self.phase * 85 + offset) % 360
            self.canvas.create_arc(
                center - 42,
                center - 42,
                center + 42,
                center + 42,
                start=start,
                extent=68,
                outline=self.theme["processing"],
                width=3,
                style=tk.ARC,
            )
        self._dot(center, self.theme["accent_2"], 4)

    def _draw_speaking(self, center: float) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.phase * 1.4)
        self._glow(center, self.theme["speaking_outer"], self.theme["speaking"], 36 + pulse * 5, intensity=0.75)
        self._ring(center, 34, self.theme["speaking"], 2)
        self._draw_waveform(center, self.theme["speaking"], self.theme["accent_2"], scale=1.2 + pulse * 0.5)

    def _draw_blocked(self, center: float) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.phase * 2.4)
        self._glow(center, self.theme["blocked_outer"], self.theme["blocked"], 37 + pulse * 7, intensity=1.0)
        self._ring(center, 36 + pulse * 3, self.theme["blocked"], 4)
        self.canvas.create_text(center, center + 1, text="!", fill="#ffd2d2", font=("Helvetica", 34, "bold"))

    def _glow(self, center: float, outer_color: str, inner_color: str, radius: float, intensity: float) -> None:
        rings = [
            (radius + 23, outer_color, max(1, int(3 * intensity))),
            (radius + 15, outer_color, max(1, int(4 * intensity))),
            (radius + 8, inner_color, max(1, int(3 * intensity))),
        ]
        for ring_radius, color, width in rings:
            self._ring(center, ring_radius, color, width)

    def _ring(self, center: float, radius: float, color: str, width: int) -> None:
        self.canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            outline=color,
            width=width,
        )

    def _dot(self, center: float, color: str, radius: float) -> None:
        self.canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            fill=color,
            outline="",
        )

    def _draw_waveform(self, center: float, left_color: str, right_color: str, scale: float) -> None:
        bar_width = 4
        gap = 5
        heights = [12, 22, 32, 24, 16]
        start_x = center - ((len(heights) - 1) * gap) / 2

        for index, height in enumerate(heights):
            wobble = 0.65 + 0.35 * math.sin(self.phase * 2.0 + index)
            scaled_height = height * scale * wobble
            x = start_x + index * gap
            color = left_color if index < 2 else right_color
            self.canvas.create_line(
                x,
                center - scaled_height / 2,
                x,
                center + scaled_height / 2,
                fill=color,
                width=bar_width,
                capstyle=tk.ROUND,
            )


def main() -> None:
    """Run the activation indicator."""
    parser = argparse.ArgumentParser(description="Run the AuraOS activation indicator.")
    parser.add_argument("--demo", action="store_true", help="Cycle through visual states.")
    parser.add_argument("--state-file", type=Path, default=STATE_FILE, help="State file to watch.")
    parser.add_argument("--position-file", type=Path, default=POSITION_FILE, help="Position file to save/load.")
    parser.add_argument("--settings-file", type=Path, default=SETTINGS_FILE, help="Settings file to save/load.")
    parser.add_argument("--size", type=int, default=136, help="Indicator window size.")
    parser.add_argument("--solid-background", action="store_true", help="Use a dark square background instead of transparency.")
    args = parser.parse_args()

    try:
        ActivationIndicator(
            state_file=args.state_file,
            position_file=args.position_file,
            settings_file=args.settings_file,
            size=args.size,
            demo=args.demo,
            transparent=not args.solid_background,
        ).run()
    except tk.TclError as error:
        print(f"Unable to start activation indicator UI: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
