import { SystemMetrics } from "../hooks";

interface SystemMonitorProps {
  metrics: SystemMetrics;
  history: { cpu: number[]; ram: number[]; gpu: (number | null)[] };
}

function Sparkline({ data, color = "#00d4ff", width = 60, height = 20 }: {
  data: (number | null)[];
  color?: string;
  width?: number;
  height?: number;
}) {
  const validData = data.filter((v): v is number => v !== null);
  if (validData.length < 2) return <div style={{ width, height }} />;

  const max = Math.max(...validData, 1);
  const points = validData.map((v, i) => {
    const x = (i / (validData.length - 1)) * width;
    const y = height - (v / max) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} style={{ overflow: "visible" }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />
      {validData.length > 0 && (
        <circle
          cx={(validData.length - 1) / (validData.length - 1) * width}
          cy={height - (validData[validData.length - 1] / max) * height}
          r="2"
          fill={color}
          opacity="0.8"
        />
      )}
    </svg>
  );
}

function MonitorCard({ label, value, unit, data, color, icon, sub }: {
  label: string;
  value: number | string | null;
  unit: string;
  data: (number | null)[];
  color: string;
  icon: React.ReactNode;
  sub?: string;
}) {
  const isNA = value === null || value === "N/A";
  return (
    <div className="panel-glass rounded-lg p-3" style={{ minHeight: 56 }}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span style={{ color: "#4a5568", fontSize: 12 }}>{icon}</span>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: "#7a8599", fontFamily: '"Space Grotesk", sans-serif' }}>
            {label}
          </span>
        </div>
        {!isNA && <Sparkline data={data} color={color} width={50} height={16} />}
      </div>
      <div className="flex items-baseline gap-1">
        <span style={{ fontSize: isNA ? 13 : 20, fontWeight: 700, fontFamily: '"Space Grotesk", sans-serif', color: isNA ? "#4a5568" : "#e0e8ff", lineHeight: 1 }}>
          {isNA ? "N/A" : value}
        </span>
        {!isNA && <span style={{ fontSize: 10, color: "#4a5568", fontWeight: 500 }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 9, color: "#4a5568", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function SystemMonitor({ metrics, history }: SystemMonitorProps) {
  const gpuLabel = metrics.gpuName
    ? typeof metrics.gpuName === "string"
      ? metrics.gpuName.replace(/NVIDIA /, "").replace(/GeForce /, "")
      : String(metrics.gpuName).replace(/NVIDIA /, "").replace(/GeForce /, "")
    : "GPU";

  const gpuSub = metrics.vramTotal
    ? `${metrics.vramUsed?.toFixed(1) ?? 0} / ${metrics.vramTotal.toFixed(1)} GB VRAM`
    : undefined;

  const cards = [
    {
      label: "CPU",
      value: metrics.cpu,
      unit: "%",
      data: history.cpu,
      color: "#00d4ff",
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <rect x="9" y="9" width="6" height="6" />
          <path d="M15 2v2M9 2v2M15 20v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2" />
        </svg>
      ),
    },
    {
      label: "RAM",
      value: metrics.ram,
      unit: "%",
      data: history.ram,
      color: "#3388ff",
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="6" width="20" height="12" rx="2" />
          <path d="M6 6V4M10 6V4M14 6V4M18 6V4M6 18v2M10 18v2M14 18v2M18 18v2" />
        </svg>
      ),
    },
    {
      label: gpuLabel,
      value: metrics.gpu,
      unit: "%",
      data: history.gpu,
      color: "#00e88a",
      sub: gpuSub,
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="2" width="20" height="20" rx="2" />
          <path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 7h5M17 17h5" />
        </svg>
      ),
    },
    {
      label: "NPU",
      value: metrics.npu,
      unit: "%",
      data: [],
      color: "#ffaa00",
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      ),
    },
  ];

  const formatBytes = (mb: number) => {
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} Gbps`;
    return `${mb.toFixed(1)} Mbps`;
  };

  return (
    <div
      className="flex flex-col rounded-xl overflow-hidden"
      style={{ width: 220, background: "rgba(8, 12, 24, 0.85)", border: "1px solid rgba(0, 212, 255, 0.1)" }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
          SYSTEM MONITOR
        </span>
      </div>

      <div className="p-2 space-y-2">
        {cards.map((card) => (
          <MonitorCard key={card.label} {...card} />
        ))}
      </div>

      {/* Network */}
      <div className="mx-2 mb-2 p-3 rounded-lg" style={{ background: "rgba(0, 212, 255, 0.03)", border: "1px solid rgba(0, 212, 255, 0.06)" }}>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: "#7a8599", fontFamily: '"Space Grotesk", sans-serif' }}>NETWORK</span>
        <div className="flex items-center gap-4 mt-1.5">
          <div className="flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00e88a" strokeWidth="2">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#e0e8ff" }}>
              {metrics.networkDown > 0 ? formatBytes(metrics.networkDown) : "N/A"}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ff4466" strokeWidth="2">
              <path d="M12 5v14M19 12l-7 7-7-7" />
            </svg>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#e0e8ff" }}>
              {metrics.networkUp > 0 ? formatBytes(metrics.networkUp) : "N/A"}
            </span>
          </div>
        </div>
      </div>

      {/* Storage */}
      <div className="mx-2 mb-2 p-3 rounded-lg" style={{ background: "rgba(0, 212, 255, 0.03)", border: "1px solid rgba(0, 212, 255, 0.06)" }}>
        <div className="flex items-center justify-between mb-1.5">
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: "#7a8599", fontFamily: '"Space Grotesk", sans-serif' }}>STORAGE</span>
        </div>
        <div className="flex items-baseline gap-1 mb-2">
          <span style={{ fontSize: 16, fontWeight: 700, color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
            {Math.round(metrics.storageUsed)}
          </span>
          <span style={{ fontSize: 10, color: "#4a5568" }}>
            GB / {Math.round(metrics.storageTotal)} GB
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, color: "#00d4ff", marginLeft: "auto" }}>
            {metrics.storageTotal > 0 ? Math.round((metrics.storageUsed / metrics.storageTotal) * 100) : 0}%
          </span>
        </div>
        <div style={{ height: 3, background: "rgba(0, 212, 255, 0.1)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: `${metrics.storageTotal > 0 ? (metrics.storageUsed / metrics.storageTotal) * 100 : 0}%`,
            background: "linear-gradient(90deg, #00d4ff, #0088ff)",
            borderRadius: 2,
            transition: "width 0.5s ease",
          }} />
        </div>
      </div>

      {/* Power */}
      <div className="mx-2 mb-2 p-3 rounded-lg" style={{ background: "rgba(0, 212, 255, 0.03)", border: "1px solid rgba(0, 212, 255, 0.06)" }}>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: "#7a8599", fontFamily: '"Space Grotesk", sans-serif' }}>POWER</span>
        {metrics.powerPercent !== null ? (
          <>
            <div className="flex items-baseline gap-1 mt-1">
              <span style={{ fontSize: 20, fontWeight: 700, color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
                {Math.round(metrics.powerPercent)}%
              </span>
            </div>
            <span style={{ fontSize: 10, fontWeight: 600, color: metrics.powerAc ? "#00d4ff" : "#ffaa00", letterSpacing: "0.05em" }}>
              {metrics.powerAc ? "AC CONNECTED" : "BATTERY"}
            </span>
          </>
        ) : (
          <div className="flex items-baseline gap-1 mt-1">
            <span style={{ fontSize: 13, fontWeight: 600, color: "#4a5568" }}>AC POWERED</span>
          </div>
        )}
      </div>

      {/* GPU Temp */}
      {metrics.gpuTemp !== null && (
        <div className="mx-2 mb-2 p-3 rounded-lg" style={{ background: "rgba(0, 212, 255, 0.03)", border: "1px solid rgba(0, 212, 255, 0.06)" }}>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: "#7a8599", fontFamily: '"Space Grotesk", sans-serif' }}>GPU TEMP</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span style={{ fontSize: 20, fontWeight: 700, color: metrics.gpuTemp > 80 ? "#ff4466" : "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
              {metrics.gpuTemp}°C
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
