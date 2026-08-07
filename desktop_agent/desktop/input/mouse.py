"""
MYRAA Desktop Control V3

Mouse Controller

Responsibilities
----------------
- Mouse movement
- Smooth movement
- Relative movement
- Position
- Screen size

No AI
No Planner
No Registry
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pyautogui

# Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


@dataclass
class MousePosition:
    x: int
    y: int


class MouseController:

    def __init__(self):

        self.default_duration = 0.25

    # -------------------------------------------------
    # INFORMATION
    # -------------------------------------------------

    def position(self) -> MousePosition:
        """Current cursor position"""

        x, y = pyautogui.position()

        return MousePosition(x=x, y=y)

    def screen_size(self) -> Tuple[int, int]:
        """Primary monitor size"""

        return pyautogui.size()

    # -------------------------------------------------
    # MOVEMENT
    # -------------------------------------------------

    def move(
        self,
        x: int,
        y: int,
        duration: float | None = None,
    ) -> bool:

        duration = duration or self.default_duration

        pyautogui.moveTo(
            x,
            y,
            duration=duration,
        )

        return True

    def move_relative(
        self,
        dx: int,
        dy: int,
        duration: float | None = None,
    ) -> bool:

        duration = duration or self.default_duration

        pyautogui.moveRel(
            dx,
            dy,
            duration=duration,
        )

        return True

    # -------------------------------------------------
    # SAFE MOVEMENT
    # -------------------------------------------------

    def move_center(self) -> bool:
        """Move cursor to screen center"""

        width, height = self.screen_size()

        return self.move(
            width // 2,
            height // 2,
        )

    def move_percentage(
        self,
        x_percent: float,
        y_percent: float,
        duration: float | None = None,
    ) -> bool:

        width, height = self.screen_size()

        x = int(width * x_percent)
        y = int(height * y_percent)

        return self.move(
            x,
            y,
            duration,
        )

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    def is_inside_screen(
        self,
        x: int,
        y: int,
    ) -> bool:

        width, height = self.screen_size()

        return (
            0 <= x <= width
            and
            0 <= y <= height
        )


        # -------------------------------------------------
    # CLICKING
    # -------------------------------------------------

    def click(
        self,
        button: str = "left",
        clicks: int = 1,
        interval: float = 0.1,
    ) -> bool:

        pyautogui.click(
            button=button,
            clicks=clicks,
            interval=interval,
        )

        return True

    def left_click(self) -> bool:

        return self.click("left")

    def right_click(self) -> bool:

        return self.click("right")

    def middle_click(self) -> bool:

        return self.click("middle")

    def double_click(
        self,
        button: str = "left",
    ) -> bool:

        return self.click(
            button=button,
            clicks=2,
            interval=0.10,
        )

    def triple_click(
        self,
        button: str = "left",
    ) -> bool:

        return self.click(
            button=button,
            clicks=3,
            interval=0.10,
        )

    # -------------------------------------------------
    # CLICK AT POSITION
    # -------------------------------------------------

    def click_at(
        self,
        x: int,
        y: int,
        button: str = "left",
        duration: float | None = None,
    ) -> bool:

        self.move(
            x,
            y,
            duration,
        )

        return self.click(button)

    def double_click_at(
        self,
        x: int,
        y: int,
    ) -> bool:

        self.move(x, y)

        return self.double_click()

    # -------------------------------------------------
    # BUTTON HOLD
    # -------------------------------------------------

    def mouse_down(
        self,
        button: str = "left",
    ) -> bool:

        pyautogui.mouseDown(button=button)

        return True

    def mouse_up(
        self,
        button: str = "left",
    ) -> bool:

        pyautogui.mouseUp(button=button)

        return True

    # -------------------------------------------------
    # DRAG
    # -------------------------------------------------

    def drag_to(
        self,
        x: int,
        y: int,
        duration: float = 0.5,
        button: str = "left",
    ) -> bool:

        pyautogui.dragTo(
            x,
            y,
            duration=duration,
            button=button,
        )

        return True

    def drag_relative(
        self,
        dx: int,
        dy: int,
        duration: float = 0.5,
        button: str = "left",
    ) -> bool:

        pyautogui.dragRel(
            dx,
            dy,
            duration=duration,
            button=button,
        )

        return True

    # -------------------------------------------------
    # SCROLL
    # -------------------------------------------------

    def scroll_up(
        self,
        amount: int = 500,
    ) -> bool:

        pyautogui.scroll(amount)

        return True

    def scroll_down(
        self,
        amount: int = 500,
    ) -> bool:

        pyautogui.scroll(-amount)

        return True

    def horizontal_scroll(
        self,
        amount: int,
    ) -> bool:

        pyautogui.hscroll(amount)

        return True

        # -------------------------------------------------
    # SAFETY
    # -------------------------------------------------

    def validate_position(
        self,
        x: int,
        y: int,
    ) -> bool:
        """
        Validate coordinates before executing movement.
        """

        return self.is_inside_screen(x, y)

    def safe_move(
        self,
        x: int,
        y: int,
        duration: float | None = None,
    ) -> bool:

        if not self.validate_position(x, y):
            return False

        return self.move(
            x,
            y,
            duration,
        )

    def safe_click(
        self,
        x: int,
        y: int,
        button: str = "left",
    ) -> bool:

        if not self.safe_move(x, y):
            return False

        return self.click(button)

    # -------------------------------------------------
    # HUMAN MODE
    # -------------------------------------------------

    def human_move(
        self,
        x: int,
        y: int,
    ) -> bool:

        pyautogui.moveTo(
            x,
            y,
            duration=0.45,
            tween=pyautogui.easeInOutQuad,
        )

        return True

    def human_click(
        self,
        x: int,
        y: int,
    ) -> bool:

        self.human_move(x, y)

        pyautogui.click()

        return True

    # -------------------------------------------------
    # UTILITIES
    # -------------------------------------------------

    def move_and_click(
        self,
        x: int,
        y: int,
    ) -> bool:

        self.move(x, y)

        self.left_click()

        return True

    def move_and_double_click(
        self,
        x: int,
        y: int,
    ) -> bool:

        self.move(x, y)

        self.double_click()

        return True

    def current_position(self):

        return self.position()

    # -------------------------------------------------
    # FAILSAFE
    # -------------------------------------------------

    def emergency_stop(self):

        pyautogui.FAILSAFE = True

    def disable_failsafe(self):

        pyautogui.FAILSAFE = False