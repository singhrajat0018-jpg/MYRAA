import { logger } from './LoggingManager';
import { eventBus } from './EventBus';

export enum ServiceState {
    STOPPED,
    STARTING,
    RUNNING,
    STOPPING
}

export class LifecycleManager {
    private static instance: LifecycleManager;
    private appState: ServiceState = ServiceState.STOPPED;

    private constructor() {}

    public static getInstance(): LifecycleManager {
        if (!LifecycleManager.instance) {
            LifecycleManager.instance = new LifecycleManager();
        }
        return LifecycleManager.instance;
    }

    public async startup(): Promise<void> {
        if (this.appState !== ServiceState.STOPPED) return;
        
        this.appState = ServiceState.STARTING;
        logger.info('Lifecycle', 'Application startup sequence initiated.');
        
        // Trigger startup events for other services
        eventBus.emit('app:starting');
        
        this.appState = ServiceState.RUNNING;
        logger.info('Lifecycle', 'Application is running.');
        eventBus.emit('app:started');
    }

    public async shutdown(): Promise<void> {
        if (this.appState !== ServiceState.RUNNING) return;
        
        this.appState = ServiceState.STOPPING;
        logger.info('Lifecycle', 'Application shutdown sequence initiated.');
        
        eventBus.emit('app:stopping');
        
        this.appState = ServiceState.STOPPED;
        logger.info('Lifecycle', 'Application stopped safely.');
        eventBus.emit('app:stopped');
    }

    public getState(): ServiceState {
        return this.appState;
    }
}
export const lifecycleManager = LifecycleManager.getInstance();
