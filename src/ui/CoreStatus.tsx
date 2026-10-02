import { BrainMetrics } from "../hooks";

interface CoreStatusProps {
  metrics: BrainMetrics;
}

export function CoreStatus({ metrics }: CoreStatusProps) {
  const statusColorMap: Record<string, string> = {
    STRONG: "#00e88a",
    ACTIVE: "#00d4ff",
    WEAK: "#ffaa00",
    OFFLINE: "#ff4466",
  };

  const rows = [
    { label: "NEURAL ACTIVITY", value: metrics.neuralActivity, color: statusColorMap[metrics.neuralActivity] || "#4a5568" },
    { label: "LEARNING MODE", value: metrics.learningMode, color: "#00d4ff" },
    { label: "RESPONSE SPEED", value: `${metrics.responseSpeed.toFixed(1)} s`, color: "#e0e8ff" },
    { label: "ACCURACY", value: `${metrics.accuracy.toFixed(1)}%`, color: "#00e88a" },
    { label: "UPTIME", value: metrics.uptime, color: "#00d4ff" },
  ];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        width: 220,
        background: "rgba(8, 12, 24, 0.85)",
        border: "1px solid rgba(0, 212, 255, 0.1)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b"
        style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.12em",
            color: "#e0e8ff",
            fontFamily: '"Space Grotesk", sans-serif',
          }}
        >
          CORE STATUS
        </span>
      </div>

      {/* Rows */}
      <div className="p-3 space-y-3">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between">
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                letterSpacing: "0.05em",
                color: "#7a8599",
              }}
            >
              {row.label}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: row.color,
                fontFamily: '"Space Grotesk", sans-serif',
                letterSpacing: "0.05em",
              }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
