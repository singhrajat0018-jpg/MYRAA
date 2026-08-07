from dataclasses import dataclass


@dataclass(slots=True)
class VisionStats:

    screenshot_time: float = 0

    ocr_time: float = 0

    shape_time: float = 0

    layout_time: float = 0

    fusion_time: float = 0

    graph_time: float = 0

    tree_time: float = 0

    analyzer_time: float = 0

    total_time: float = 0