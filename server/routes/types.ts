import type { RequestHandler } from "express";

export type LogFn = (msg: string) => void;

export interface ServerContext {
  DESKTOP_AGENT_URL: string;
  LOGS_DIR: string;
  WS_SESSION_TOKEN: string;
  logCommand: LogFn;
  logError: LogFn;
}
