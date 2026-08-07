import dotenv from "dotenv";

dotenv.config();

const DESKTOP_AGENT_URL =
    process.env.DESKTOP_AGENT_URL ||
    "http://127.0.0.1:8765";

const DESKTOP_AGENT_TIMEOUT = 25_000;

let desktopAgentVerified = false;

// ------------------------------------------------------------

async function isDesktopAgentAlive(): Promise<boolean> {

    try {

        const controller = new AbortController();

        const timer = setTimeout(
            () => controller.abort(),
            3000,
        );

        const response = await fetch(
            `${DESKTOP_AGENT_URL}/health`,
            {
                signal: controller.signal,
            },
        );

        clearTimeout(timer);

        return response.ok;

    } catch {

        return false;

    }

}

// ------------------------------------------------------------

export async function ensureDesktopAgent(): Promise<void> {

    if (desktopAgentVerified) {

        return;

    }

    const alive =
        await isDesktopAgentAlive();

    if (!alive) {

        throw new Error(

            "Desktop Agent is not running.\n" +

            "Please start MYRAA using start-myraa.bat."

        );

    }

    desktopAgentVerified = true;

    console.log(
        "[Desktop Agent] Connected successfully."
    );

}

// ------------------------------------------------------------

export async function callDesktopAgent(

    tool: string,

    args: Record<string, unknown>,

): Promise<{

    ok: boolean;

    result?: unknown;

    error?: string;

}> {

    await ensureDesktopAgent();

    const controller =
        new AbortController();

    const timer = setTimeout(

        () => controller.abort(),

        DESKTOP_AGENT_TIMEOUT,

    );

    try {

        const response = await fetch(

            `${DESKTOP_AGENT_URL}/execute`,

            {

                method: "POST",

                headers: {

                    "Content-Type":
                        "application/json",

                },

                body: JSON.stringify({

                    tool,

                    args,

                }),

                signal: controller.signal,

            },

        );

        clearTimeout(timer);

        return await response.json();

    }

    catch (e: any) {

        clearTimeout(timer);

        return {

            ok: false,

            error: e.message,

        };

    }

}

// ------------------------------------------------------------

export async function callBrain(

    text: string,

    context?: unknown,

): Promise<{

    ok: boolean;

    result?: unknown;

    error?: string;

}> {

    await ensureDesktopAgent();

    const requestId =
        Math.random()

            .toString(36)

            .slice(2, 8);

    console.log(

        `[Brain ${requestId}] Sending:`,

        text,

    );

    const controller =
        new AbortController();

    const timer = setTimeout(

        () => controller.abort(),

        DESKTOP_AGENT_TIMEOUT,

    );

    try {

        const response = await fetch(

            `${DESKTOP_AGENT_URL}/brain`,

            {

                method: "POST",

                headers: {

                    "Content-Type":
                        "application/json",

                },

                body: JSON.stringify({

                    text,

                    context,

                }),

                signal:
                    controller.signal,

            },

        );

        console.log(

            `[Brain ${requestId}] Response received`

        );

        clearTimeout(timer);

        return await response.json();

    }

    catch (e: any) {

        clearTimeout(timer);

        return {

            ok: false,

            error: e.message,

        };

    }

}