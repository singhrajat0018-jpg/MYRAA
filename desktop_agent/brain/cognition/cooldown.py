from __future__ import annotations

from datetime import datetime, timedelta


class Cooldown:

    NOTIFICATION = timedelta(minutes=5)

    PLANNER = timedelta(minutes=2)

    @staticmethod
    def expired(last_time, duration):

        if last_time is None:
            return True

        return datetime.utcnow() - last_time >= duration