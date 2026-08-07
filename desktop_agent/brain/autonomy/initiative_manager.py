from __future__ import annotations

import time


class InitiativeManager:

    def __init__(self):

        self.active = {}

        self.cooldown = 60.0

    # ----------------------------

    def allow(self, initiative):

        key = initiative.title

        now = time.time()

        last = self.active.get(key)

        if last is None:

            self.active[key] = now

            return True

        if now - last >= self.cooldown:

            self.active[key] = now

            return True

        return False

    # ----------------------------

    def clear(self, title):

        self.active.pop(title, None)

    # ----------------------------

    def reset(self):

        self.active.clear()