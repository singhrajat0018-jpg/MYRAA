import dotenv from "dotenv";
import crypto from "crypto";

dotenv.config();

export const DESKTOP_AGENT_URL =
    process.env.DESKTOP_AGENT_URL ||
    "http://127.0.0.1:8765";

const DESKTOP_AGENT_TIMEOUT = 25_000;

let desktopAgentVerified = false;
let lastVerifiedAt = 0;

// Phase 29.7: liveness cache has a TTL — never trust a stale "alive" forever.
const LIVENESS_TTL_MS = 30_000;

export function invalidateDesktopAgentLiveness(): void {
    desktopAgentVerified = false;
    lastVerifiedAt = 0;
}

// ------------------------------------------------------------

async function isDesktopAgentAlive(): Promise<boolean> {

    try {

        const controller = new AbortController();

        const timer = setTimeout(
            () => controller.abort(),
            3000,
        );

        const response = await fetch(
            `${DESKTOP_AGENT_URL}/health/live`,
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

export async function ensureDesktopAgent(throwOnFail = false): Promise<boolean> {

    const cacheIsFresh =
        desktopAgentVerified && (Date.now() - lastVerifiedAt) < LIVENESS_TTL_MS;

    if (cacheIsFresh) {

        return true;

    }

    const alive =
        await isDesktopAgentAlive();

    if (!alive) {

        desktopAgentVerified = false;
        lastVerifiedAt = 0;

        if (throwOnFail) {
            throw new Error(
                "Desktop Agent is not running.\n" +
                "Please start MYRAA using start-myraa.bat."
            );
        }

        return false;

    }

    desktopAgentVerified = true;
    lastVerifiedAt = Date.now();

    console.log(
        "[Desktop Agent] Connected successfully."
    );

    return true;

}

// ------------------------------------------------------------

export async function callDesktopAgent(

    tool: string,

    args: Record<string, unknown>,

    opts?: {

        requestId?: string;

        taskId?: string;

    },

): Promise<{

    ok: boolean;

    result?: unknown;

    error?: string;

}> {

    const alive = await ensureDesktopAgent(false);
    if (!alive) {
        return {
            ok: false,
            error: "Desktop Agent is offline in this environment.",
        };
    }

    const controller = new AbortController();

    const timer = setTimeout(() => controller.abort(), DESKTOP_AGENT_TIMEOUT);

    const requestId =
        opts?.requestId ||
        crypto.randomUUID();

    try {

        const response = await fetch(
            `${DESKTOP_AGENT_URL}/execute`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Request-ID": requestId,
                },
                body: JSON.stringify({
                    tool,
                    args,
                    request_id: requestId,
                    task_id: opts?.taskId,
                }),
                signal: controller.signal,
            },
        );

        clearTimeout(timer);

        const body = await response.json();

        // Surface the request id in the result for end-to-end traceability.
        if (body && typeof body === "object") {
            if (body.meta && typeof body.meta === "object") {
                if (!body.meta.request_id) body.meta.request_id = requestId;
            } else {
                body.meta = { request_id: requestId };
            }
        }

        return body;

    }

    catch (e: any) {

        clearTimeout(timer);

        // Phase 29.7: connection-level failures invalidate cached liveness.
        const msg = String(e?.message || "");
        if (msg.includes("ECONNREFUSED") || msg.includes("fetch failed") || msg.includes("timed out") || msg.includes("abort")) {
            invalidateDesktopAgentLiveness();
        }

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

    opts?: {

        requestId?: string;

        taskId?: string;

    },

): Promise<{

    ok: boolean;

    result?: unknown;

    error?: string;

}> {

    const alive = await ensureDesktopAgent(false);
    if (!alive) {
        return {
            ok: false,
            error: "Desktop Agent is offline in this environment.",
        };
    }

    const requestId =
        opts?.requestId ||
        crypto.randomUUID();

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

                    "X-Request-ID":
                        requestId,

                },

                body: JSON.stringify({

                    text,

                    context,

                    request_id: requestId,

                    task_id: opts?.taskId,

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