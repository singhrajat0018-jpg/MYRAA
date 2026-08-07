from enum import Enum


class IntentType(str, Enum):

    IGNORE = "ignore"

    REMEMBER = "remember"

    NOTIFY = "notify"

    PLAN = "plan"

    ACT = "act"