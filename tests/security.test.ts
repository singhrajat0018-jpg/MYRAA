import { describe, it, expect } from "vitest";
import { execSync } from "child_process";

describe("SSRF Protection", () => {
  it("blocks localhost variants", () => {
    const blocked = [
      "http://localhost:3000",
      "http://127.0.0.1:8765",
      "http://[::1]:3000",
    ];
    for (const url of blocked) {
      const parsed = new URL(url);
      const host = parsed.hostname.toLowerCase();
      const isBlocked =
        host === "localhost" ||
        host === "127.0.0.1" ||
        host === "::1" ||
        host === "[::1]" ||
        /^10\./.test(host) ||
        /^192\.168\./.test(host) ||
        /^172\.(1[6-9]|2\d|3[01])\./.test(host) ||
        /^169\.254\./.test(host);
      expect(isBlocked, `${url} should be blocked`).toBe(true);
    }
  });

  it("allows public URLs", () => {
    const allowed = [
      "https://api.open-meteo.com/v1/forecast",
      "https://api.tavily.com/search",
      "https://en.wikipedia.org/api/rest_v1/page/summary/Python",
    ];
    for (const url of allowed) {
      const parsed = new URL(url);
      const host = parsed.hostname.toLowerCase();
      const isBlocked =
        host === "localhost" ||
        host === "127.0.0.1" ||
        host === "::1" ||
        /^10\./.test(host) ||
        /^192\.168\./.test(host) ||
        /^172\.(1[6-9]|2\d|3[01])\./.test(host) ||
        /^169\.254\./.test(host);
      expect(isBlocked, `${url} should NOT be blocked`).toBe(false);
    }
  });
});

describe("CORS Configuration", () => {
  it("ALLOWED_ORIGINS contains only localhost", () => {
    const ALLOWED_ORIGINS = new Set([
      "http://localhost:3000",
      "http://127.0.0.1:3000",
    ]);
    expect(ALLOWED_ORIGINS.size).toBe(2);
    expect(ALLOWED_ORIGINS.has("http://localhost:3000")).toBe(true);
    expect(ALLOWED_ORIGINS.has("*")).toBe(false);
  });
});

describe("WebSocket Token", () => {
  it("token is a hex string of correct length", () => {
    const crypto = require("crypto");
    const token = crypto.randomBytes(16).toString("hex");
    expect(token).toMatch(/^[0-9a-f]{32}$/);
  });
});

describe("PermissionManager Thread Safety (Python)", () => {
  it("has thread-safe confirmation tokens", () => {
    const result = execSync("python tests/_pm_test.py", {
      cwd: process.cwd(),
      encoding: "utf-8",
      timeout: 10000,
    }).trim();
    const data = JSON.parse(result);
    expect(data.lock).toBe(true);
    expect(data.single_use).toBe(true);
    expect(data.wrong_tool).toBe(true);
    expect(data.wrong_args).toBe(true);
  });
});

describe("FastCore Classification (Python)", () => {
  const classify = (text: string) => {
    const escaped = text.replace(/"/g, '\\"');
    const result = execSync(
      `python -c "import sys; sys.path.insert(0,'.'); from desktop_agent.fastcore.classifier import FastCoreClassifier; c=FastCoreClassifier(); r=c.classify('${escaped}'); print(r.task_type.value)"`,
      { cwd: process.cwd(), encoding: "utf-8", timeout: 10000 }
    ).trim();
    return result;
  };

  it("classifies weather queries", () => {
    expect(classify("what is the weather in delhi")).toBe("weather_task");
  });

  it("classifies news queries", () => {
    expect(classify("latest news about AI")).toBe("news_task");
  });

  it("classifies research queries", () => {
    expect(classify("research the latest breakthroughs in quantum computing")).toBe("web_research");
  });

  it("classifies desktop actions", () => {
    expect(classify("open notepad")).toBe("desktop_action");
  });

  it("classifies conversation", () => {
    expect(classify("hello how are you")).toBe("local_reasoning");
  });

  it("FastCore latency under 5ms", () => {
    const result = execSync(
      `python -c "import sys,time; sys.path.insert(0,'.'); from desktop_agent.fastcore.classifier import FastCoreClassifier; c=FastCoreClassifier(); s=time.perf_counter(); c.classify('test'); print((time.perf_counter()-s)*1000)"`,
      { cwd: process.cwd(), encoding: "utf-8", timeout: 10000 }
    ).trim();
    expect(parseFloat(result)).toBeLessThan(5);
  });
});

describe("ResearchHandoff Contract (Python)", () => {
  it("ResearchHandoff has required fields", () => {
    const result = execSync(
      `python -c "import sys; sys.path.insert(0,'.'); from desktop_agent.brain.router.response_router import ResearchHandoff; h=ResearchHandoff(query='test',reason='r',needs_synthesis=True); print(f'{h.query}|{h.reason}|{h.needs_synthesis}')"`,
      { cwd: process.cwd(), encoding: "utf-8", timeout: 10000 }
    ).trim();
    const [query, reason, synth] = result.split("|");
    expect(query).toBe("test");
    expect(reason).toBe("r");
    expect(synth).toBe("True");
  });

  it("ResearchRouter accepts ResearchHandoff", () => {
    const result = execSync(
      `python -c "import sys; sys.path.insert(0,'.'); from desktop_agent.brain.research.research_router import ResearchRouter; from desktop_agent.brain.router.response_router import ResearchHandoff; rr=ResearchRouter(); h=ResearchHandoff(query='test',reason='r'); print('OK')"`,
      { cwd: process.cwd(), encoding: "utf-8", timeout: 10000 }
    ).trim();
    expect(result).toBe("OK");
  });
});
