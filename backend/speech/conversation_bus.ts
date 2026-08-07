export interface ConversationTurn {

    role: "user" | "assistant";

    text: string;

    timestamp: number;

}

export class ConversationBus {

    private history: ConversationTurn[] = [];

    private readonly MAX_HISTORY = 20;

    addUser(text: string) {

        this.push({
            role: "user",
            text,
            timestamp: Date.now(),
        });

    }

    addAssistant(text: string) {

        this.push({
            role: "assistant",
            text,
            timestamp: Date.now(),
        });

    }

    private push(turn: ConversationTurn) {

        this.history.push(turn);

        if (this.history.length > this.MAX_HISTORY) {

            this.history.shift();

        }

    }

    snapshot() {

        return [...this.history];

    }

    clear() {

        this.history = [];

    }

}