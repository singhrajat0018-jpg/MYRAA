from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeConfig:

    brain_fps: int = 2

    autonomous: bool = True

    proactive: bool = True

    vision_enabled: bool = True

    observation_fps: int = 2

    prediction_enabled: bool = True

    initiative_enabled: bool = True

    reflection_enabled: bool = True

    learning_enabled: bool = True

    max_autonomous_actions: int = 5