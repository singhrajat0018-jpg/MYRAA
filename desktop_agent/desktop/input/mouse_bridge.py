"""
MYRAA Mouse Tool Bridge

Connects Planner MouseAdapter
with Desktop MouseController
"""

from __future__ import annotations

from .mouse import MouseController


class MouseToolBridge:

    def __init__(self):

        self.mouse = MouseController()


    async def click(
        self,
        x=None,
        y=None,
    ):

        if x is not None and y is not None:
            return self.mouse.click_at(
                x,
                y
            )

        return self.mouse.left_click()


    async def double_click(
        self,
        x=None,
        y=None,
    ):

        if x is not None and y is not None:
            return self.mouse.double_click_at(
                x,
                y
            )

        return self.mouse.double_click()


    async def right_click(
        self,
        x=None,
        y=None,
    ):

        if x is not None and y is not None:
            self.mouse.move(x,y)

        return self.mouse.right_click()



    async def middle_click(
        self,
        x=None,
        y=None,
    ):

        if x is not None and y is not None:
            self.mouse.move(x,y)

        return self.mouse.middle_click()



    async def move_mouse(
        self,
        x,
        y,
    ):

        return self.mouse.move(
            x,
            y
        )


    async def drag(
        self,
        start,
        end,
    ):

        self.mouse.move(
            start["x"],
            start["y"]
        )

        return self.mouse.drag_to(
            end["x"],
            end["y"]
        )


    async def drop(self):

        return True


    async def scroll(
        self,
        direction,
        amount=1,
    ):

        if direction == "up":
            return self.mouse.scroll_up(amount)

        return self.mouse.scroll_down(amount)



    async def hover(
        self,
        x,
        y,
    ):

        return self.mouse.move(
            x,
            y
        )