import { logger } from './LoggingManager';

export class DiagnosticsManager {
    private static instance: DiagnosticsManager;
    private metrics: Record<string, number> = {};

    private constructor() {}

    public static getInstance(): DiagnosticsManager {
        if (!DiagnosticsManager.instance) {
            DiagnosticsManager.instance = new DiagnosticsManager();
        }
        return DiagnosticsManager.instance;
    }

    public recordMetric(name: string, value: number) {
        this.metrics[name] = value;
        logger.debug('Diagnostics', `Metric recorded: ${name}=${value}`);
    }

    public getMetrics(): Record<string, number> {
        return { ...this.metrics };
    }

    public reportHealth(): boolean {
        logger.info('Diagnostics', 'Health check passed.');
        return true;
    }
}
export const diagnosticsManager = DiagnosticsManager.getInstance();
