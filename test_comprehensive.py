import time
import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from desktop_agent.brain.observer.observers.screen_observer import ScreenObserver
    
    print('Creating ScreenObserver with adaptive FPS...')
    obs = ScreenObserver(
        name='comprehensive_test',
        capture_fps=8,  # Start at 8 FPS
        process_fps=3,  # Process at 3 FPS
        change_threshold=0.02,
        ocr_interval=3.0,
        min_capture_fps=4,
        max_capture_fps=12,
        activity_threshold=0.05
    )
    
    print('ScreenObserver created: {}'.format(obs.name))
    print('Initial capture FPS: {}'.format(obs.capture_fps))
    print('Min capture FPS: {}'.format(obs.min_capture_fps))
    print('Max capture FPS: {}'.format(obs.max_capture_fps))
    print('Activity threshold: {}'.format(obs.activity_threshold))
    
    # Test starting and stopping
    print('\nStarting observer...')
    obs.start()
    print('Observer started')
    
    # Run for 15 seconds to see FPS adaptation
    print('\nRunning for 15 seconds to test FPS adaptation...')
    start_time = time.time()
    last_fps_check = start_time
    
    while time.time() - start_time < 15:
        time.sleep(1)
        
        # Check FPS every 2 seconds
        if time.time() - last_fps_check >= 2:
            print('Current FPS: {}, Change history length: {}'.format(
                obs.capture_fps, 
                len(obs._change_history) if hasattr(obs, '_change_history') else 0
            ))
            last_fps_check = time.time()
    
    # Poll for events
    print('\nPolling for events...')
    events = obs.poll()
    print('Got {} events'.format(len(events)))
    
    # Show event types
    event_types = {}
    for event in events:
        event_type = event.title
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    print('Event breakdown:')
    for event_type, count in event_types.items():
        print('  {}: {}'.format(event_type, count))
    
    print('\nStopping observer...')
    obs.stop()
    print('Observer stopped')
    
    print('\nFinal status: {}'.format(obs.get_status()))
    print('\nTest completed successfully!')
    
except Exception as e:
    print('Error during test: {}'.format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)
