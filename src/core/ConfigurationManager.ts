export class ConfigurationManager {
    private static instance: ConfigurationManager;
    private config: Map<string, any> = new Map();

    private constructor() {}

    public static getInstance(): ConfigurationManager {
        if (!ConfigurationManager.instance) {
            ConfigurationManager.instance = new ConfigurationManager();
        }
        return ConfigurationManager.instance;
    }

    public set(key: string, value: any): void {
        this.config.set(key, value);
    }

    public get<T>(key: string, defaultValue?: T): T | undefined {
        if (this.config.has(key)) {
            return this.config.get(key) as T;
        }
        return defaultValue;
    }
}
export const configManager = ConfigurationManager.getInstance();
