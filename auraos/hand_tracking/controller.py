"""Map gestures to local cursor actions."""

from __future__ import annotations

import time


class CursorController:
    """Small pyautogui adapter with smoothing and click cooldown."""

    def __init__(self, smoothing: float = 0.55, click_cooldown: float = 0.6, edge_margin: float = 0.12) -> None:
        pyautogui = _require_pyautogui()
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0

        self._pyautogui = pyautogui
        self.screen_width, self.screen_height = pyautogui.size()
        self.smoothing = smoothing
        self.click_cooldown = click_cooldown
        self.edge_margin = edge_margin
        self._last_x: int | None = None
        self._last_y: int | None = None
        self._last_click_time = 0.0

    def move_to_normalized(self, x_norm: float, y_norm: float, mirror: bool = True) -> None:
        if mirror:
            x_norm = 1.0 - x_norm

        x_norm = _expand_from_inner_area(x_norm, self.edge_margin)
        y_norm = _expand_from_inner_area(y_norm, self.edge_margin)
        target_x = _clamp(int(x_norm * self.screen_width), 0, self.screen_width - 1)
        target_y = _clamp(int(y_norm * self.screen_height), 0, self.screen_height - 1)

        if self._last_x is None or self._last_y is None:
            next_x, next_y = target_x, target_y
        else:
            next_x = int(self._last_x + (target_x - self._last_x) * self.smoothing)
            next_y = int(self._last_y + (target_y - self._last_y) * self.smoothing)

        self._last_x = next_x
        self._last_y = next_y
        self._pyautogui.moveTo(next_x, next_y)

    def click(self) -> bool:
        now = time.time()
        if now - self._last_click_time < self.click_cooldown:
            return False

        self._last_click_time = now
        self._pyautogui.click()
        return True

    def right_click(self) -> None:
        self._pyautogui.click(button="right")

    def double_click(self) -> None:
        self._pyautogui.doubleClick()

    def drag_down(self) -> None:
        self._pyautogui.mouseDown()

    def drag_up(self) -> None:
        self._pyautogui.mouseUp()

    def scroll(self, direction: str, amount: int = 300) -> None:
        if direction == "up":
            self._pyautogui.scroll(amount)
        elif direction == "down":
            self._pyautogui.scroll(-amount)

    def hotkey(self, *keys: str) -> None:
        self._pyautogui.hotkey(*keys)

    def press(self, key: str) -> None:
        self._pyautogui.press(key)

    def browser_back(self) -> None:
        self.hotkey("command", "[")

    def browser_forward(self) -> None:
        self.hotkey("command", "]")

    def previous_desktop(self) -> None:
        self.hotkey("ctrl", "left")

    def next_desktop(self) -> None:
        self.hotkey("ctrl", "right")

    def mission_control(self) -> None:
        self.hotkey("ctrl", "up")

    def show_desktop(self) -> None:
        self.hotkey("command", "f3")

    def refresh_page(self) -> None:
        self.hotkey("command", "r")

    def new_tab(self) -> None:
        self.hotkey("command", "t")

    def close_tab(self) -> None:
        self.hotkey("command", "w")

    def play_pause(self) -> None:
        self.press("playpause")

    def next_track(self) -> None:
        self.press("nexttrack")

    def previous_track(self) -> None:
        self.press("prevtrack")

    def volume_up(self) -> None:
        self.press("volumeup")

    def volume_down(self) -> None:
        self.press("volumedown")


def _require_pyautogui():
    try:
        import pyautogui
    except ImportError as error:
        raise RuntimeError(
            "Cursor control requires pyautogui. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return pyautogui


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _expand_from_inner_area(value: float, margin: float) -> float:
    if margin <= 0:
        return float(value)

    inner_span = 1.0 - (2.0 * margin)
    if inner_span <= 0:
        return float(value)

    expanded = (value - margin) / inner_span
    return max(0.0, min(expanded, 1.0))
