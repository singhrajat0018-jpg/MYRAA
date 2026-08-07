import { logger } from './LoggingManager';

export interface AIProvider {
    generateText(prompt: string): Promise<string>;
}

export class AIManager {
    private static instance: AIManager;
    private provider: AIProvider | null = null;

    private constructor() {}

    public static getInstance(): AIManager {
        if (!AIManager.instance) {
            AIManager.instance = new AIManager();
        }
        return AIManager.instance;
    }

    public setProvider(provider: AIProvider): void {
        this.provider = provider;
        logger.info('AIManager', 'AI Provider registered.');
    }

    public async processPrompt(prompt: string): Promise<string> {
        if (!this.provider) {
            logger.error('AIManager', 'No AI Provider registered.');
            throw new Error('AI Provider not initialized');
        }
        return await this.provider.generateText(prompt);
    }
}
export const aiManager = AIManager.getInstance();
