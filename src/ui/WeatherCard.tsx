import { WeatherData } from "../hooks";

interface WeatherCardProps {
  data: WeatherData;
}

export function WeatherCard({ data }: WeatherCardProps) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ flex: 1, minWidth: 260, background: "rgba(8, 12, 24, 0.85)", border: "1px solid rgba(0, 212, 255, 0.1)" }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
          WEATHER
        </span>
      </div>

      <div className="p-4">
        {data.loading ? (
          <div className="flex items-center justify-center py-6">
            <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            <div className="flex items-start gap-4">
              <div className="flex items-center gap-3">
                <span style={{ fontSize: 36 }}>{data.icon}</span>
                <div>
                  <div className="flex items-baseline gap-1">
                    <span style={{ fontSize: 28, fontWeight: 700, fontFamily: '"Space Grotesk", sans-serif', color: "#e0e8ff", lineHeight: 1 }}>
                      {data.temp !== null ? `${data.temp}°C` : "N/A"}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: "#7a8599" }}>{data.condition}</span>
                  {data.locationName && (
                    <div style={{ fontSize: 10, color: "#4a5568", marginTop: 2 }}>{data.locationName}</div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-6 mt-4 pt-3 border-t" style={{ borderColor: "rgba(0, 212, 255, 0.06)" }}>
              <div>
                <div style={{ fontSize: 9, color: "#4a5568", letterSpacing: "0.05em" }}>Humidity</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#e0e8ff" }}>{data.humidity !== null ? `${data.humidity}%` : "N/A"}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "#4a5568", letterSpacing: "0.05em" }}>Wind</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#e0e8ff" }}>{data.wind !== null ? `${data.wind} km/h` : "N/A"}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "#4a5568", letterSpacing: "0.05em" }}>Feels like</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#e0e8ff" }}>{data.feelsLike !== null ? `${data.feelsLike}°C` : "N/A"}</div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
