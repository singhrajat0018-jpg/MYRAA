import { ModuleStatus } from "../hooks";

interface ActiveModulesProps {
  modules: ModuleStatus;
}

const MODULE_LIST = [
  { key: "voiceEngine" as const, label: "VOICE ENGINE" },
  { key: "visionSystem" as const, label: "VISION SYSTEM" },
  { key: "memoryCore" as const, label: "MEMORY CORE" },
  { key: "browserAgent" as const, label: "BROWSER AGENT" },
  { key: "fileSystem" as const, label: "FILE SYSTEM" },
  { key: "researchAgent" as const, label: "RESEARCH AGENT" },
  { key: "autonomyEngine" as const, label: "AUTONOMY ENGINE" },
  { key: "selfHealing" as const, label: "SELF-HEALING" },
];

export function ActiveModules({ modules }: ActiveModulesProps) {
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
          ACTIVE MODULES
        </span>
      </div>

      {/* Module list */}
      <div className="p-3 space-y-2">
        {MODULE_LIST.map((mod) => {
          const isOn = modules[mod.key];
          return (
            <div key={mod.key} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="status-dot"
                  style={{
                    background: isOn ? "#00e88a" : "#4a5568",
                    boxShadow: isOn ? "0 0 6px rgba(0, 232, 138, 0.4)" : "none",
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 500,
                    color: isOn ? "#e0e8ff" : "#4a5568",
                    letterSpacing: "0.05em",
                  }}
                >
                  {mod.label}
                </span>
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: isOn ? "#00e88a" : "#4a5568",
                  fontFamily: '"Space Grotesk", sans-serif',
                }}
              >
                {isOn ? "ON" : "OFF"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
