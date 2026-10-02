import { useState, useEffect, useCallback } from "react";

interface VoiceHUDItem {
  id: string;
  type: "weather" | "news" | "info";
  title: string;
  value: string;
  subtitle?: string;
  timestamp: number;
}

interface VoiceHUDProps {
  metadata?: Record<string, unknown>;
}

const HUD_LIFETIME_MS = 6000;

export function VoiceHUD({ metadata }: VoiceHUDProps) {
  const [items, setItems] = useState<VoiceHUDItem[]>([]);

  const addItem = useCallback((item: Omit<VoiceHUDItem, "id" | "timestamp">) => {
    const newItem: VoiceHUDItem = {
      ...item,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: Date.now(),
    };
    setItems(prev => [...prev, newItem]);
  }, []);

  useEffect(() => {
    if (!metadata) return;
    const intent = metadata.intent as string | undefined;
    const data = metadata.data as Record<string, unknown> | undefined;

    if (intent === "weather_task" && data) {
      addItem({
        type: "weather",
        title: "WEATHER",
        value: data.temp ? `${data.temp}°C` : (data.condition as string) || "Loading",
        subtitle: data.location as string | undefined,
      });
    } else if (intent === "news_task" && data) {
      const count = (data.items as unknown[])?.length || 0;
      addItem({
        type: "news",
        title: "NEWS",
        value: `${count} RESULT${count !== 1 ? "S" : ""}`,
        subtitle: (data.category as string) || undefined,
      });
    } else if (metadata.provider || metadata.model_route) {
      addItem({
        type: "info",
        title: (metadata.model_route as string)?.toUpperCase() || "THINKING",
        value: metadata.provider as string || "",
      });
    }
  }, [metadata, addItem]);

  useEffect(() => {
    if (items.length === 0) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setItems(prev => prev.filter(item => now - item.timestamp < HUD_LIFETIME_MS));
    }, 500);
    return () => clearInterval(timer);
  }, [items.length]);

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col items-center gap-2 pointer-events-none">
      {items.map(item => {
        const age = Date.now() - item.timestamp;
        const opacity = Math.max(0, 1 - age / HUD_LIFETIME_MS);
        const translateY = Math.min(0, (age / HUD_LIFETIME_MS) * 8);

        return (
          <div
            key={item.id}
            className="flex flex-col items-center transition-all duration-300"
            style={{
              opacity,
              transform: `translateY(${translateY}px)`,
            }}
          >
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.15em",
                color: item.type === "weather" ? "var(--color-myraa-voice)" : item.type === "news" ? "var(--color-status-warning)" : "var(--color-text-accent)",
                fontFamily: "var(--font-display)",
              }}
            >
              {item.title}
            </div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                fontFamily: "var(--font-display)",
                color: "var(--color-text-primary)",
                lineHeight: 1.2,
              }}
            >
              {item.value}
            </div>
            {item.subtitle && (
              <div
                style={{
                  fontSize: 9,
                  color: "var(--color-text-muted)",
                  letterSpacing: "0.05em",
                  marginTop: 1,
                }}
              >
                {item.subtitle}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
