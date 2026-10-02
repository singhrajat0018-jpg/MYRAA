import time
import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from desktop_agent.brain.observer.observers.screen_observer import ScreenObserver
    
    # Test screen observer creation
    print('Creating screen observer...')
    obs = ScreenObserver(
        name='test_observer',
        capture_fps=5,
        process_fps=2,
        change_threshold=0.01,
        ocr_interval=2.0
    )
    print('ScreenObserver created: {}'.format(obs.name))
    
    # Test that it has the poll method
    print('Has poll method: {}'.format(hasattr(obs, "poll")))
    print('Poll method: {}'.format(obs.poll))
    
    # Test starting and stopping
    print('Starting observer...')
    obs.start()
    print('Observer started')
    
    # Give it a moment to start capturing
    time.sleep(5)
    
    # Poll for events
    print('Polling for events...')
    events = obs.poll()
    print('Got {} events'.format(len(events)))
    
    for i, event in enumerate(events):
        # Simple print without Unicode characters
        title = event.title.encode('ascii', 'ignore').decode('ascii')
        message = event.message.encode('ascii', 'ignore').decode('ascii')
        print('Event {}: {} - {}'.format(i, title, message))
        if hasattr(event, 'data') and event.data:
            print('  Data keys: {}'.format(list(event.data.keys())))
    
    print('Stopping observer...')
    obs.stop()
    print('Observer stopped')
    
    print('Test completed successfully!')
    
except Exception as e:
    print('Error during test: {}'.format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)
