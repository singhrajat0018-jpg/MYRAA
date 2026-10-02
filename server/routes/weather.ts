import type { ServerContext } from "./types";

export function registerWeatherRoutes(app: any, ctx: ServerContext) {
  app.get("/api/weather", async (req: any, res: any) => {
    try {
      const lat = parseFloat(req.query.lat as string) || 28.6139;
      const lon = parseFloat(req.query.lon as string) || 77.2090;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 5000);
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto`;
      const r = await fetch(url, { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) {
        const data = await r.json();
        const current = data.current;
        const wmoCodes: Record<number, string> = {
          0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
          45: "Foggy", 48: "Rime Fog", 51: "Light Drizzle", 53: "Moderate Drizzle",
          55: "Dense Drizzle", 61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
          71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow", 80: "Slight Showers",
          81: "Moderate Showers", 82: "Violent Showers", 95: "Thunderstorm",
          96: "Thunderstorm + Hail", 99: "Thunderstorm + Heavy Hail",
        };
        const wmoIcon: Record<number, string> = {
          0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
          45: "🌫️", 48: "🌫️", 51: "🌦️", 53: "🌦️",
          55: "🌧️", 61: "🌧️", 63: "🌧️", 65: "🌧️",
          71: "❄️", 73: "❄️", 75: "❄️", 80: "🌦️",
          81: "🌧️", 82: "⛈️", 95: "⛈️",
          96: "⛈️", 99: "⛈️",
        };
        const code = current.weather_code || 0;
        res.json({
          temp: Math.round(current.temperature_2m),
          feelsLike: Math.round(current.apparent_temperature),
          condition: wmoCodes[code] || "Unknown",
          icon: wmoIcon[code] || "🌤️",
          humidity: current.relative_humidity_2m,
          wind: Math.round(current.wind_speed_10m),
          lat,
          lon,
        });
      } else {
        res.json({ temp: null, condition: "Unavailable", icon: "❓" });
      }
    } catch {
      res.json({ temp: null, condition: "Unavailable", icon: "❓" });
    }
  });

  app.get("/api/news", async (req: any, res: any) => {
    try {
      const query = (req.query.q as string) || "latest news";
      const category = req.query.category as string | undefined;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 10000);
      const params = new URLSearchParams({ q: query });
      if (category) params.set("category", category);
      const r = await fetch(`${ctx.DESKTOP_AGENT_URL}/news?${params}`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) {
        res.json(await r.json());
      } else {
        res.json({ items: [], error: "Provider returned " + r.status, count: 0 });
      }
    } catch {
      res.json({ items: [], error: "News service unavailable", count: 0 });
    }
  });
}
