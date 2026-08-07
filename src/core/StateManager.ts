import { EventBus } from './EventBus';

export class StateManager<T extends object> {
    private state: T;
    private eventBus: EventBus;
    private context: string;

    constructor(initialState: T, context: string) {
        this.state = { ...initialState };
        this.eventBus = EventBus.getInstance();
        this.context = context;
    }

    public getState(): Readonly<T> {
        return Object.freeze({ ...this.state });
    }

    public updateState(partialState: Partial<T>): void {
        this.state = { ...this.state, ...partialState };
        this.eventBus.emit(`${this.context}:stateChanged`, this.state);
    }
}
