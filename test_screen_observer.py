import time
import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from desktop_agent.brain.observer.observers.screen_observer import ScreenObserver
    from desktop_agent.desktop.vision.live_capture import LiveCaptureEngine
    from desktop_agent.desktop.vision.frame_difference import FrameDifference
    from desktop_agent.desktop.vision.ocr_engine import OCREngine
    from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import TesseractBackend as TesseractOCR
    from desktop_agent.brain.observer.event import ObserverEvent, EventType, EventSeverity
    
    # Test screen observer creation
    print('Creating screen observer...')
    obs = ScreenObserver(
        name='test_observer',
        capture_fps=5,
        process_fps=2,
        change_threshold=0.01,
        ocr_interval=2.0
    )
    print(f'ScreenObserver created: {obs.name}')
    
    # Test that it has the poll method
    print(f'Has poll method: {hasattr(obs, "poll")}')
    print(f'Poll method: {obs.poll}')
    
    # Test starting and stopping
    print('Starting observer...')
    obs.start()
    print('Observer started')
    
    # Give it a moment to start capturing
    time.sleep(3)
    
    # Poll for events
    print('Polling for events...')
    events = obs.poll()
    print(f'Got {len(events)} events')
    
    for i, event in enumerate(events):
        print(f'Event {i}: {event.title} - {event.message}')
        if hasattr(event, 'data'):
            print(f'  Data keys: {list(event.data.keys()) if event.data else "None"}')
    
    print('Stopping observer...')
    obs.stop()
    print('Observer stopped')
    
    print('Test completed successfully!')
    
except Exception as e:
    print(f'Error during test: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
