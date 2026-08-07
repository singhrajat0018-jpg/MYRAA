export enum LogLevel {
    DEBUG,
    INFO,
    WARN,
    ERROR
}

export class LoggingManager {
    private static instance: LoggingManager;
    private currentLevel: LogLevel = LogLevel.INFO;

    private constructor() {}

    public static getInstance(): LoggingManager {
        if (!LoggingManager.instance) {
            LoggingManager.instance = new LoggingManager();
        }
        return LoggingManager.instance;
    }

    public setLevel(level: LogLevel) {
        this.currentLevel = level;
    }

    public debug(context: string, message: string, ...args: any[]) {
        if (this.currentLevel <= LogLevel.DEBUG) {
            console.debug(`[DEBUG] [${context}] ${message}`, ...args);
        }
    }

    public info(context: string, message: string, ...args: any[]) {
        if (this.currentLevel <= LogLevel.INFO) {
            console.info(`[INFO]  [${context}] ${message}`, ...args);
        }
    }

    public warn(context: string, message: string, ...args: any[]) {
        if (this.currentLevel <= LogLevel.WARN) {
            console.warn(`[WARN]  [${context}] ${message}`, ...args);
        }
    }

    public error(context: string, message: string, error?: any, ...args: any[]) {
        if (this.currentLevel <= LogLevel.ERROR) {
            console.error(`[ERROR] [${context}] ${message}`, error || '', ...args);
        }
    }
}
export const logger = LoggingManager.getInstance();
