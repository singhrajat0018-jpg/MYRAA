/**
 * System Diagnostics Workspace
 *
 * Shows real system health from Python /health/ready + Node telemetry.
 */
import React, { useEffect, useState } from "react";
import { useAppStore } from "../core/store";
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Wifi,
  Server,
  Brain,
  Eye,
  Mic,
  BarChart3,
  Shield,
  RefreshCw,
} from "lucide-react";

interface DiagnosticResult {
  component: string;
  status: string;
  latency_ms: number;
  last_error: string | null;
  last_recovery: string | null;
}

interface HealthData {
  status: string;
  version: string;
  tool_count: number;
  system: { cpu_percent: number; ram_percent: number; disk_usage_percent: number };
  subsystems: Record<string, { status: string; consecutive_failures: number }>;
  dependencies?: Record<string, { configured: boolean; available: boolean; state: string }>;
}

export default function SystemWorkspace() {
  const { state } = useAppStore();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastFetch, setLastFetch] = useState<number>(0);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/agent-health");
      if (r.ok) {
        const data = await r.json();
        // Merge with telemetry data
        setHealth({
          status: data.online ? "ok" : "offline",
          version: data.version || "unknown",
          tool_count: data.tool_count || 0,
          system: data.system || { cpu_percent: 0, ram_percent: 0, disk_usage_percent: 0 },
          subsystems: {},
        });
        setLastFetch(Date.now());
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchHealth(); }, []);

  const subsystems = [
    { name: "VOICE", connected: state.voice.connected, icon: Mic },
    { name: "PYTHON", connected: state.system.pythonConnection === "connected", icon: Server },
    { name: "NODE", connected: state.system.nodeConnection === "connected", icon: Wifi },
    { name: "TRADING", connected: state.trading.connected, icon: BarChart3 },
  ];

  return (
    <div className="w-full h-full overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-white tracking-tight">
            System <span className="text-cyan-400">Diagnostics</span>
          </h1>
          <p className="text-xs font-mono text-gray-500 mt-1">
            Real-time backend health
          </p>
        </div>
        <button
          onClick={fetchHealth}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono text-gray-400 hover:text-white bg-white/5 border border-white/10 rounded-lg transition cursor-pointer"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Core Status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatusCard
          icon={Activity}
          label="HEALTH"
          value={health?.status?.toUpperCase() || "CHECKING"}
          ok={health?.status === "ok"}
        />
        <StatusCard
          icon={Cpu}
          label="CPU"
          value={`${state.system.cpuPercent.toFixed(1)}%`}
          ok={state.system.cpuPercent < 80}
        />
        <StatusCard
          icon={MemoryStick}
          label="RAM"
          value={`${state.system.ramPercent.toFixed(1)}%`}
          ok={state.system.ramPercent < 80}
        />
        <StatusCard
          icon={HardDrive}
          label="DISK"
          value={`${state.system.diskPercent.toFixed(1)}%`}
          ok={state.system.diskPercent < 90}
        />
      </div>

      {/* Subsystems */}
      <div className="mb-6">
        <h2 className="text-xs font-mono text-gray-400 tracking-widest mb-3">SUBSYSTEMS</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {subsystems.map(s => (
            <div key={s.name} className="rounded-xl bg-white/[0.02] border border-white/5 p-3">
              <div className="flex items-center gap-2 mb-2">
                <s.icon size={14} className="text-gray-500" />
                <span className="text-[10px] font-mono text-gray-400">{s.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${s.connected ? "bg-emerald-400" : "bg-red-400"}`} />
                <span className={`text-xs font-mono ${s.connected ? "text-emerald-400" : "text-red-400"}`}>
                  {s.connected ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tool Count */}
      {health && (
        <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4 mb-6">
          <h2 className="text-xs font-mono text-gray-400 tracking-widest mb-2">REGISTERED TOOLS</h2>
          <div className="text-2xl font-mono font-bold text-cyan-400">{health.tool_count}</div>
          <p className="text-[10px] font-mono text-gray-600 mt-1">Desktop control tools available</p>
        </div>
      )}

      {/* Telemetry Stream */}
      <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4">
        <h2 className="text-xs font-mono text-gray-400 tracking-widest mb-3">RECENT TELEMETRY</h2>
        {state.telemetry.length === 0 ? (
          <p className="text-xs font-mono text-gray-600">No telemetry events yet</p>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {state.telemetry.slice(-20).reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-gray-500 py-1 border-b border-white/[0.02]">
                <span className="text-gray-600">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className="text-gray-400 w-20 truncate">{e.component}</span>
                <span className="text-cyan-400/50 w-24 truncate">{e.route || e.tool}</span>
                <span className={e.status === "ok" ? "text-emerald-400/50" : "text-red-400/50"}>
                  {e.status}
                </span>
                {e.latency_ms > 0 && <span className="text-gray-600 ml-auto">{e.latency_ms}ms</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({ icon: Icon, label, value, ok }: { icon: React.ElementType; label: string; value: string; ok: boolean }) {
  return (
    <div className={`rounded-xl bg-white/[0.02] border p-3 ${ok ? "border-emerald-500/20" : "border-red-500/20"}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={12} className="text-gray-500" />
        <span className="text-[9px] font-mono tracking-widest text-gray-500">{label}</span>
      </div>
      <div className={`text-sm font-mono font-bold ${ok ? "text-emerald-400" : "text-red-400"}`}>{value}</div>
    </div>
  );
}
