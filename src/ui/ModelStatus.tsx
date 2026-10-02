import { ModelHealth } from "../hooks";

interface ModelStatusProps {
  models: ModelHealth;
}

const MODEL_LIST = [
  { key: "fastcore" as const, label: "FASTCORE", color: "#00d4ff" },
  { key: "qwen" as const, label: "QWEN 3.5", color: "#3388ff" },
  { key: "gemma" as const, label: "GEMMA 3", color: "#00e88a" },
  { key: "minimax" as const, label: "MINIMAX", color: "#ffaa00" },
];

export function ModelStatus({ models }: ModelStatusProps) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        width: 220,
        background: "rgba(8, 12, 24, 0.85)",
        border: "1px solid rgba(0, 212, 255, 0.1)",
      }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
          LOCAL MODELS
        </span>
      </div>
      <div className="p-3 space-y-2">
        {MODEL_LIST.map((mod) => {
          const status = models[mod.key];
          const isReady = status === "READY";
          return (
            <div key={mod.key} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="status-dot"
                  style={{
                    background: isReady ? mod.color : "#4a5568",
                    boxShadow: isReady ? `0 0 6px ${mod.color}40` : "none",
                  }}
                />
                <span style={{ fontSize: 10, fontWeight: 500, color: isReady ? "#e0e8ff" : "#4a5568", letterSpacing: "0.05em" }}>
                  {mod.label}
                </span>
              </div>
              <span style={{ fontSize: 10, fontWeight: 700, color: isReady ? mod.color : "#4a5568", fontFamily: '"Space Grotesk", sans-serif' }}>
                {status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
