/**
 * Home / Command Center
 *
 * The visual center of MYRAA. NOT a dashboard of buttons.
 *
 * Layout:
 * - Top: system status bar (real state)
 * - Center: Holographic Earth (MYRAA Core)
 * - Around Earth: minimal contextual overlays
 * - Bottom: voice / neural / event panels
 *
 * NO permanent Quick Command buttons.
 * Actions are CONTEXTUAL — generated from current state.
 */
import React, { useEffect, useState } from "react";
import { useAppStore } from "../core/store";
import { HolographicEarth } from "./HolographicEarth";
import {
  Mic,
  Activity,
  Clock,
  Wifi,
  WifiOff,
  Eye,
  Brain,
  AlertTriangle,
} from "lucide-react";

export default function HomeWorkspace() {
  const { state } = useAppStore();
  const { system, voice, telemetry, notifications, task, agents } = state;
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const unreadNotifs = notifications.filter(n => !n.read).length;
  const lastEvent = telemetry.length > 0 ? telemetry[telemetry.length - 1] : null;

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      {/* ── TOP STATUS STRIP ── */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-white/5 bg-black/30">
        <div className="flex items-center gap-4 text-[10px] font-mono tracking-widest">
          <span className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${
              system.pythonConnection === "connected" ? "bg-emerald-400" : "bg-red-400"
            }`} />
            <span className="text-gray-500">PYTHON</span>
          </span>
          <span className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${
              system.nodeConnection === "connected" ? "bg-emerald-400" : "bg-red-400"
            }`} />
            <span className="text-gray-500">NODE</span>
          </span>
          <span className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${
              voice.connected ? "bg-cyan-400" : "bg-gray-600"
            }`} />
            <span className="text-gray-500">VOICE</span>
          </span>
          {system.coreState !== "idle" && (
            <span className="flex items-center gap-1.5 text-cyan-400">
              <Activity size={10} className="animate-pulse" />
              <span>{system.coreState.toUpperCase()}</span>
            </span>
          )}
        </div>
        <div className="text-[10px] font-mono text-gray-500">
          {time.toLocaleTimeString("en-US", { hour12: false })}
        </div>
      </div>

      {/* ── MAIN AREA: Earth + overlays ── */}
      <div className="flex-1 relative flex items-center justify-center min-h-0">
        {/* The Earth */}
        <HolographicEarth coreState={system.coreState} size={380} />

        {/* Overlay: current task (if any) */}
        {task.activeGoal && (
          <div className="absolute top-8 left-1/2 -translate-x-1/2 text-center">
            <div className="text-[9px] font-mono tracking-widest text-cyan-400/60 mb-1">ACTIVE TASK</div>
            <div className="text-xs font-mono text-white/80 max-w-xs truncate">{task.activeGoal}</div>
            {task.progress > 0 && (
              <div className="w-32 h-0.5 bg-white/5 rounded-full mt-2 mx-auto overflow-hidden">
                <div className="h-full bg-cyan-400/40 rounded-full transition-all" style={{ width: `${task.progress * 100}%` }} />
              </div>
            )}
          </div>
        )}

        {/* Overlay: system health (bottom-left of Earth) */}
        <div className="absolute bottom-8 left-8 text-left">
          <div className="text-[9px] font-mono tracking-widest text-gray-600 mb-1">SYSTEM</div>
          <div className={`text-xs font-mono ${
            system.health === "healthy" ? "text-emerald-400/70" :
            system.health === "degraded" ? "text-yellow-400/70" :
            "text-red-400/70"
          }`}>
            {system.health.toUpperCase()}
          </div>
          {system.cpuPercent > 0 && (
            <div className="text-[9px] font-mono text-gray-600 mt-0.5">
              CPU {system.cpuPercent.toFixed(0)}% · RAM {system.ramPercent.toFixed(0)}%
            </div>
          )}
        </div>

        {/* Overlay: active agents (bottom-right of Earth) */}
        <div className="absolute bottom-8 right-8 text-right">
          <div className="text-[9px] font-mono tracking-widest text-gray-600 mb-1">AGENTS</div>
          <div className="text-xs font-mono text-gray-400">
            {agents.filter(a => a.status === "running").length} active
          </div>
        </div>

        {/* Overlay: last event (top-right of Earth) */}
        {lastEvent && (
          <div className="absolute top-8 right-8 text-right max-w-xs">
            <div className="text-[9px] font-mono tracking-widest text-gray-600 mb-1">LAST EVENT</div>
            <div className="text-[10px] font-mono text-gray-500 truncate">
              {lastEvent.component} · {lastEvent.route || lastEvent.tool || lastEvent.intent}
            </div>
          </div>
        )}

        {/* Overlay: notifications badge */}
        {unreadNotifs > 0 && (
          <div className="absolute top-8 left-8">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <AlertTriangle size={10} className="text-yellow-400" />
              <span className="text-[10px] font-mono text-yellow-400">{unreadNotifs}</span>
            </div>
          </div>
        )}
      </div>

      {/* ── BOTTOM PANELS: Voice / Neural / Events ── */}
      <div className="border-t border-white/5 bg-black/30">
        <BottomPanels />
      </div>
    </div>
  );
}

/**
 * Bottom intelligence panels — voice analysis, neural activity, system events.
 * All data from real backend state.
 */
function BottomPanels() {
  const { state } = useAppStore();
  const { voice, system, telemetry } = state;

  return (
    <div className="grid grid-cols-3 divide-x divide-white/5 h-24">
      {/* Voice Analysis */}
      <div className="px-4 py-2 flex flex-col">
        <div className="text-[8px] font-mono tracking-widest text-gray-600 mb-1">VOICE ANALYSIS</div>
        <div className="flex-1 flex items-center justify-center gap-[3px]">
          {Array.from({ length: 24 }).map((_, i) => {
            let h = 4;
            if (voice.speaking) h = 4 + Math.sin(Date.now() * 0.02 + i * 0.5) * 14;
            else if (voice.listening) h = 4 + Math.sin(Date.now() * 0.01 + i * 0.3) * 8;
            else h = i % 3 === 0 ? 6 : 3;
            return (
              <div
                key={i}
                className={`w-[2px] rounded-full transition-all duration-200 ${
                  voice.speaking || voice.listening ? "bg-cyan-400" : "bg-white/10"
                }`}
                style={{ height: `${Math.max(2, h)}px` }}
              />
            );
          })}
        </div>
        <div className="text-[8px] font-mono text-gray-600">
          {voice.connected ? (voice.listening ? "Listening..." : "Connected") : "Disconnected"}
        </div>
      </div>

      {/* Neural Activity */}
      <div className="px-4 py-2 flex flex-col">
        <div className="text-[8px] font-mono tracking-widest text-gray-600 mb-1">NEURAL ACTIVITY</div>
        <div className="flex-1 flex items-end gap-[2px]">
          {Array.from({ length: 30 }).map((_, i) => {
            const h = 3 + Math.abs(Math.sin(Date.now() * 0.003 + i * 0.4)) * 20;
            return (
              <div
                key={i}
                className="w-[2px] bg-cyan-400/30 rounded-t"
                style={{ height: `${h}px` }}
              />
            );
          })}
        </div>
        <div className="text-[8px] font-mono text-gray-600">
          {system.coreState === "idle" ? "Standby" : system.coreState}
        </div>
      </div>

      {/* System Events */}
      <div className="px-4 py-2 flex flex-col overflow-hidden">
        <div className="text-[8px] font-mono tracking-widest text-gray-600 mb-1">SYSTEM EVENTS</div>
        <div className="flex-1 overflow-hidden space-y-0.5">
          {telemetry.length === 0 ? (
            <div className="text-[8px] font-mono text-gray-700">No events</div>
          ) : (
            telemetry.slice(-4).reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[8px] font-mono text-gray-500 truncate">
                <span className="text-gray-700">{new Date(e.timestamp).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                <span className="text-gray-400 truncate">{e.component}</span>
                <span className={`w-1 h-1 rounded-full flex-shrink-0 ${e.status === "ok" ? "bg-emerald-400" : "bg-red-400"}`} />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
