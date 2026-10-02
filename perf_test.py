import time
import random
from desktop_agent.desktop.vision.screen_state_builder import screen_state_builder
from desktop_agent.desktop.vision.desktop_state import DesktopState
from desktop_agent.desktop.vision.vision_context import VisionContext
from desktop_agent.desktop.vision.fusion_engine import SemanticScreen, SemanticNode, SemanticRole
from desktop_agent.desktop.vision.layout_analyzer import LayoutType, Rect
from desktop_agent.desktop.vision.text_region import TextRegion
from desktop_agent.desktop.vision.spatial_graph import SpatialGraph
from desktop_agent.desktop.vision.semantic_tree import SemanticTree

def create_mock_semantic_node(node_id: int) -> SemanticNode:
    # Create a random bounding box
    x = random.randint(0, 1920)
    y = random.randint(0, 1080)
    width = random.randint(10, 200)
    height = random.randint(10, 100)

    # Create a random layout (can be None)
    layout = random.choice([None] + list(LayoutType)) if random.random() > 0.5 else None

    # Create a random semantic role
    role = random.choice(list(SemanticRole))

    # Create random text
    text = f"Text {node_id}" if random.random() > 0.2 else ""

    # Create a mock Rect for bounds
    bounds = Rect(x=x, y=y, width=width, height=height)

    return SemanticNode(
        node_id=node_id,
        role=role,
        text=text,
        layout=layout,
        shape=None,  # We don't need to mock shape for this test
        bounds=bounds,
        source_text=None,  # We don't need to mock source_text for this test
        confidence=random.uniform(0.7, 0.95),
        source="mock",
        merged=False
    )

def create_mock_desktop_state(node_count: int) -> DesktopState:
    nodes = [create_mock_semantic_node(i) for i in range(node_count)]

    # Create a mock screen (SemanticScreen)
    screen = SemanticScreen(
        width=1920,
        height=1080,
        nodes=nodes
    )

    # Create a mock vision context
    vision_context = VisionContext(
        screen=screen,
        graph=SpatialGraph(),
        tree=SemanticTree()
    )

    # Create a mock desktop state
    desktop_state = DesktopState()
    desktop_state.timestamp = time.time()
    desktop_state.vision_context = vision_context
    desktop_state.screen_summary = None  # We don't have a mock ScreenSummary, so set to None
    desktop_state.active_window_title = "Mock Window"
    desktop_state.active_application = "mock_app.exe"
    desktop_state.active_window_hwnd = 12345
    desktop_state.confidence = 0.9
    # The node_count and ready properties are derived, so we don't set them directly

    return desktop_state

def main():
    print("Performance test for ScreenStateBuilder")
    print("=" * 50)

    # Test with different numbers of nodes
    test_counts = [10, 50, 100, 200]

    for node_count in test_counts:
        print(f"\nTesting with {node_count} semantic nodes:")

        # Create a mock desktop state
        desktop_state = create_mock_desktop_state(node_count)

        # Warm up
        for _ in range(5):
            screen_state_builder.build_screen_state(desktop_state)

        # Measure performance
        iterations = 50
        start_time = time.time()
        for _ in range(iterations):
            screen_state = screen_state_builder.build_screen_state(desktop_state)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / iterations
        fps = 1.0 / avg_time if avg_time > 0 else float('inf')

        print(f"  Average time per build: {avg_time*1000:.2f} ms")
        print(f"  FPS: {fps:.2f}")

        # Check if it meets the requirement (4-15 FPS)
        if fps >= 4.0:
            print(f"  [PASS] Meets minimum FPS requirement (>= 4 FPS)")
        else:
            print(f"  [FAIL] Below minimum FPS requirement (< 4 FPS)")

        if fps <= 15.0:
            print(f"  [PASS] Within maximum FPS expectation (<= 15 FPS)")
        else:
            print(f"  [PASS] Above maximum FPS expectation (> 15 FPS) - still acceptable for perception layer")

    print("\n" + "=" * 50)
    print("Performance test completed.")

if __name__ == "__main__":
    main()