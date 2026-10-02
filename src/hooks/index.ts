import { useState, useEffect, useRef } from "react";

// ─── System Metrics (polled from Python /system/metrics) ────────────────────
export interface SystemMetrics {
  cpu: number;
  ram: number;
  gpu: number | null;
  gpuName: string | null;
  vramUsed: number | null;
  vramTotal: number | null;
  gpuTemp: number | null;
  npu: number | null;
  networkDown: number;
  networkUp: number;
  storageUsed: number;
  storageTotal: number;
  powerPercent: number | null;
  powerAc: boolean;
}

const defaultMetrics: SystemMetrics = {
  cpu: 0, ram: 0, gpu: null, gpuName: null,
  vramUsed: null, vramTotal: null, gpuTemp: null, npu: null,
  networkDown: 0, networkUp: 0,
  storageUsed: 0, storageTotal: 1,
  powerPercent: null, powerAc: true,
};

export function useSystemMetrics(intervalMs = 3000) {
  const [metrics, setMetrics] = useState<SystemMetrics>(defaultMetrics);
  const [history, setHistory] = useState<{ cpu: number[]; ram: number[]; gpu: (number | null)[] }>({
    cpu: [], ram: [], gpu: [],
  });
  const [netHistory, setNetHistory] = useState<{ down: number[]; up: number[] }>({ down: [], up: [] });
  const prevNetRef = useRef<{ down: number; up: number; time: number } | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const resp = await fetch("http://127.0.0.1:8765/system/metrics", {
          signal: AbortSignal.timeout(4000),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!alive) return;

        // Calculate network speed (bytes delta / time delta)
        const now = Date.now();
        let netDown = 0;
        let netUp = 0;
        if (prevNetRef.current) {
          const dt = (now - prevNetRef.current.time) / 1000;
          if (dt > 0) {
            netDown = Math.max(0, (data.network_down - prevNetRef.current.down) / dt);
            netUp = Math.max(0, (data.network_up - prevNetRef.current.up) / dt);
          }
        }
        prevNetRef.current = { down: data.network_down, up: data.network_up, time: now };

        const m: SystemMetrics = {
          cpu: data.cpu ?? 0,
          ram: data.ram ?? 0,
          gpu: data.gpu,
          gpuName: data.gpu_name,
          vramUsed: data.vram_used,
          vramTotal: data.vram_total,
          gpuTemp: data.gpu_temp,
          npu: data.npu,
          networkDown: netDown,
          networkUp: netUp,
          storageUsed: data.storage_used ?? 0,
          storageTotal: data.storage_total ?? 1,
          powerPercent: data.power_percent,
          powerAc: data.power_ac ?? true,
        };
        setMetrics(m);
        setHistory(prev => ({
          cpu: [...prev.cpu.slice(-29), m.cpu],
          ram: [...prev.ram.slice(-29), m.ram],
          gpu: [...prev.gpu.slice(-29), m.gpu],
        }));
        setNetHistory(prev => ({
          down: [...prev.down.slice(-29), netDown],
          up: [...prev.up.slice(-29), netUp],
        }));
      } catch {
        // Agent offline — keep last known values
      }
    };
    poll();
    const id = setInterval(poll, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);

  return { metrics, history, netHistory };
}

// ─── Weather (geolocation + Open-Meteo) ─────────────────────────────────────
export interface WeatherData {
  temp: number | null;
  feelsLike: number | null;
  condition: string;
  icon: string;
  humidity: number | null;
  wind: number | null;
  locationName: string;
  loading: boolean;
}

export function useWeather() {
  const [weather, setWeather] = useState<WeatherData>({
    temp: null, feelsLike: null, condition: "Loading...", icon: "🌤️",
    humidity: null, wind: null, locationName: "", loading: true,
  });

  useEffect(() => {
    let alive = true;

    const fetchWeather = async (lat: number, lon: number) => {
      try {
        const resp = await fetch(`/api/weather?lat=${lat}&lon=${lon}`, {
          signal: AbortSignal.timeout(5000),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!alive) return;
        setWeather({
          temp: data.temp,
          feelsLike: data.feelsLike,
          condition: data.condition || "Unknown",
          icon: data.icon || "🌤️",
          humidity: data.humidity,
          wind: data.wind,
          locationName: `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`,
          loading: false,
        });
      } catch {
        if (alive) setWeather(prev => ({ ...prev, condition: "Unavailable", loading: false }));
      }
    };

    // Try browser geolocation first
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (alive) fetchWeather(pos.coords.latitude, pos.coords.longitude);
        },
        () => {
          // Permission denied or unavailable — use default (New Delhi)
          if (alive) fetchWeather(28.6139, 77.2090);
        },
        { timeout: 5000, maximumAge: 300000 }
      );
    } else {
      fetchWeather(28.6139, 77.2090);
    }

    return () => { alive = false; };
  }, []);

  return weather;
}

// ─── Agent Health ───────────────────────────────────────────────────────────
export interface AgentHealth {
  pythonOnline: boolean;
  toolCount: number;
}

export function useAgentHealth(intervalMs = 8000) {
  const [health, setHealth] = useState<AgentHealth>({ pythonOnline: false, toolCount: 0 });

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const resp = await fetch("/api/agent-health", { signal: AbortSignal.timeout(3000) });
        if (!resp.ok) return;
        const data = await resp.json();
        if (alive) setHealth({ pythonOnline: data.online ?? false, toolCount: data.tool_count ?? 0 });
      } catch {
        if (alive) setHealth(prev => ({ ...prev, pythonOnline: false }));
      }
    };
    poll();
    const id = setInterval(poll, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);

  return health;
}

// ─── Telemetry Events ──────────────────────────────────────────────────────
export interface TelemetryEvent {
  event_type: string;
  payload: Record<string, unknown>;
  request_id: string;
  task_id: string;
  timestamp: number;
}

export function useTelemetry(maxEvents = 50) {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/telemetry`);

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "telemetry" && Array.isArray(data.events)) {
          setEvents(prev => [...data.events, ...prev].slice(0, maxEvents));
        }
      } catch { /* ignore */ }
    };

    return () => { ws.close(); };
  }, [maxEvents]);

  return events;
}

// ─── Clock ──────────────────────────────────────────────────────────────────
export function useClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

// ─── Active Module Status (real backend health) ────────────────────────────
export interface ModuleStatus {
  voiceEngine: boolean;
  visionSystem: boolean;
  memoryCore: boolean;
  browserAgent: boolean;
  fileSystem: boolean;
  researchAgent: boolean;
  autonomyEngine: boolean;
  selfHealing: boolean;
}

export function useModuleStatus(
  voiceState: string,
  isScreenSharing: boolean,
  memoryCount: number,
  pythonOnline: boolean,
) {
  const [subsystems, setSubsystems] = useState<Record<string, any>>({});

  useEffect(() => {
    if (!pythonOnline) { setSubsystems({}); return; }
    let alive = true;
    const poll = async () => {
      try {
        const resp = await fetch("http://127.0.0.1:8765/health", { signal: AbortSignal.timeout(3000) });
        if (!resp.ok) return;
        const data = await resp.json();
        if (alive && data.subsystems) setSubsystems(data.subsystems);
      } catch { /* keep last */ }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => { alive = false; clearInterval(id); };
  }, [pythonOnline]);

  return {
    voiceEngine: voiceState !== "disconnected",
    visionSystem: isScreenSharing || (subsystems.vision === "healthy"),
    memoryCore: memoryCount > 0 || pythonOnline,
    browserAgent: pythonOnline && subsystems.browser !== "error",
    fileSystem: pythonOnline,
    researchAgent: pythonOnline,
    autonomyEngine: pythonOnline && subsystems.action_execution !== "error",
    selfHealing: pythonOnline,
  } as ModuleStatus;
}

// ─── Brain Metrics (real data) ──────────────────────────────────────────────
export interface BrainMetrics {
  neuralActivity: "STRONG" | "ACTIVE" | "WEAK" | "OFFLINE";
  learningMode: "ADAPTIVE" | "STANDARD" | "CONSERVATIVE";
  responseSpeed: number;
  accuracy: number | null; // null = no measurement
  uptime: string;
}

export function useBrainMetrics(voiceState: string, pythonOnline: boolean) {
  const startTimeRef = useRef(Date.now());
  const lastLatencyRef = useRef(1.2);
  const [metrics, setMetrics] = useState<BrainMetrics>({
    neuralActivity: "ACTIVE",
    learningMode: "ADAPTIVE",
    responseSpeed: 1.2,
    accuracy: null,
    uptime: "0H 0M",
  });

  // Poll actual latency from telemetry
  useEffect(() => {
    if (!pythonOnline) return;
    let alive = true;
    const poll = async () => {
      try {
        const resp = await fetch("http://127.0.0.1:8765/telemetry/stream?count=5", {
          signal: AbortSignal.timeout(2000),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!alive) return;
        if (data.events?.length) {
          const latencies = data.events
            .filter((e: any) => e.payload?.latency_ms > 0)
            .map((e: any) => e.payload.latency_ms);
          if (latencies.length) {
            const avg = latencies.reduce((a: number, b: number) => a + b, 0) / latencies.length;
            lastLatencyRef.current = Math.round(avg) / 1000;
          }
        }
      } catch { /* keep last */ }
    };
    poll();
    const id = setInterval(poll, 8000);
    return () => { alive = false; clearInterval(id); };
  }, [pythonOnline]);

  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      const hours = Math.floor(elapsed / 3600000);
      const minutes = Math.floor((elapsed % 3600000) / 60000);
      const secs = Math.floor((elapsed % 60000) / 1000);

      let activity: BrainMetrics["neuralActivity"] = "ACTIVE";
      if (!pythonOnline) activity = "OFFLINE";
      else if (voiceState === "speaking") activity = "STRONG";
      else if (voiceState === "connecting") activity = "WEAK";

      setMetrics(prev => ({
        ...prev,
        neuralActivity: activity,
        responseSpeed: lastLatencyRef.current,
        uptime: hours > 0
          ? `${hours}D ${minutes}H ${secs}M`
          : `${minutes}M ${secs}S`,
      }));
    }, 1000);
    return () => clearInterval(id);
  }, [voiceState, pythonOnline]);

  return metrics;
}

// ─── Model Health (Ollama model status) ────────────────────────────────────
export interface ModelHealth {
  fastcore: "READY" | "LOADING" | "ERROR" | "OFFLINE";
  qwen: "READY" | "LOADING" | "ERROR" | "OFFLINE";
  gemma: "READY" | "LOADING" | "ERROR" | "OFFLINE";
  minimax: "READY" | "LOADING" | "ERROR" | "OFFLINE";
}

export function useModelHealth(intervalMs = 15000) {
  const [health, setHealth] = useState<ModelHealth>({
    fastcore: "OFFLINE", qwen: "OFFLINE", gemma: "OFFLINE", minimax: "OFFLINE",
  });

  useEffect(() => {
    let alive = true;
    const checkOllama = async () => {
      try {
        const resp = await fetch("http://127.0.0.1:11434/api/tags", { signal: AbortSignal.timeout(3000) });
        if (!resp.ok) {
          if (alive) setHealth({ fastcore: "OFFLINE", qwen: "OFFLINE", gemma: "OFFLINE", minimax: "OFFLINE" });
          return;
        }
        const data = await resp.json();
        const models: string[] = (data.models || []).map((m: any) => m.name?.toLowerCase() || "");
        if (alive) setHealth({
          fastcore: "READY", // FastCore is deterministic, always ready
          qwen: models.some(m => m.includes("qwen")) ? "READY" : "OFFLINE",
          gemma: models.some(m => m.includes("gemma")) ? "READY" : "OFFLINE",
          minimax: models.some(m => m.includes("minimax")) ? "READY" : "OFFLINE",
        });
      } catch {
        if (alive) setHealth({ fastcore: "READY", qwen: "OFFLINE", gemma: "OFFLINE", minimax: "OFFLINE" });
      }
    };
    checkOllama();
    const id = setInterval(checkOllama, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);

  return health;
}
