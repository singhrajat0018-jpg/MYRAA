/**
 * Agent Workspace
 *
 * Shows real active workers/agents from the Python skills system.
 */
import React, { useEffect, useState } from "react";
import { useAppStore } from "../core/store";
import { Bot, Play, Pause, X, RefreshCw, CheckCircle, AlertCircle, Clock } from "lucide-react";

export default function AgentWorkspace() {
  const { state } = useAppStore();
  const { agents } = state;

  const statusColor = (s: string) => {
    switch (s) {
      case "running": return "text-cyan-400 bg-cyan-500/10 border-cyan-500/20";
      case "completed": return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "failed": return "text-red-400 bg-red-500/10 border-red-500/20";
      case "queued": return "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
      case "waiting": return "text-orange-400 bg-orange-500/10 border-orange-500/20";
      case "verifying": return "text-purple-400 bg-purple-500/10 border-purple-500/20";
      default: return "text-gray-400 bg-gray-500/10 border-gray-500/20";
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-display font-bold text-white tracking-tight">
          Agent <span className="text-cyan-400">Workspace</span>
        </h1>
        <p className="text-xs font-mono text-gray-500 mt-1">
          Multi-agent orchestration status
        </p>
      </div>

      {agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Bot size={48} className="text-cyan-400/20 mb-4" />
          <p className="text-sm font-mono text-gray-500">No active agents</p>
          <p className="text-xs font-mono text-gray-600 mt-1">
            Agents start when you give MYRAA a complex task
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map(agent => (
            <div
              key={agent.id}
              className="rounded-xl bg-white/[0.02] border border-white/5 p-4 hover:border-cyan-500/10 transition"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <Bot size={16} className="text-cyan-400/50" />
                  <div>
                    <span className="text-sm font-mono text-white">{agent.name}</span>
                    <span className="text-[10px] font-mono text-gray-600 ml-2">{agent.skill}</span>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${statusColor(agent.status)}`}>
                  {agent.status.toUpperCase()}
                </span>
              </div>

              {agent.currentStep && (
                <div className="text-xs font-mono text-gray-400 mb-2">
                  Step: {agent.currentStep}
                </div>
              )}

              {/* Progress bar */}
              <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-cyan-400 rounded-full transition-all duration-300"
                  style={{ width: `${agent.progress * 100}%` }}
                />
              </div>

              <div className="flex items-center gap-4 text-[10px] font-mono text-gray-600">
                <span>{(agent.progress * 100).toFixed(0)}%</span>
                {agent.latency > 0 && <span>{agent.latency}ms</span>}
                {agent.result && <span className="text-emerald-400/50">Result available</span>}
                {agent.error && <span className="text-red-400/50">{agent.error}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
