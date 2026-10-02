import { useState, useEffect } from "react";
import { RefreshCw, ExternalLink, Newspaper } from "lucide-react";

interface NewsItem {
  title: string;
  url: string;
  snippet: string;
  source: string;
  published_date: string;
}

interface NewsData {
  items: NewsItem[];
  query: string;
  count: number;
  error?: string;
  timestamp?: number;
}

interface NewsCardProps {
  data?: NewsData;
  onRefresh?: () => void;
}

export function NewsCard({ data, onRefresh }: NewsCardProps) {
  const [loading, setLoading] = useState(!data);
  const [news, setNews] = useState<NewsData | null>(data || null);

  useEffect(() => {
    if (!news) fetchNews();
  }, []);

  const fetchNews = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/news?q=latest+news&category=technology");
      const d = await r.json();
      setNews(d);
    } catch {
      setNews({ items: [], query: "latest news", count: 0, error: "Unavailable" });
    }
    setLoading(false);
  };

  const displayItems = news?.items?.slice(0, 4) || [];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "rgba(8, 12, 24, 0.85)",
        border: "1px solid rgba(0, 212, 255, 0.1)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}
      >
        <div className="flex items-center gap-2">
          <Newspaper size={12} style={{ color: "#00d4ff" }} />
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.12em",
              color: "#e0e8ff",
              fontFamily: '"Space Grotesk", sans-serif',
            }}
          >
            LATEST NEWS
          </span>
        </div>
        <button
          onClick={() => { fetchNews(); onRefresh?.(); }}
          className="p-1 rounded hover:bg-white/5"
          style={{ color: "#4a5568" }}
        >
          <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Content */}
      <div className="p-3 space-y-2">
        {loading && (
          <div style={{ fontSize: 11, color: "#4a5568", textAlign: "center", padding: "12px 0" }}>
            Loading news...
          </div>
        )}

        {!loading && news?.error && (
          <div style={{ fontSize: 11, color: "#ef4444", textAlign: "center", padding: "12px 0" }}>
            {news.error}
          </div>
        )}

        {!loading && displayItems.length === 0 && !news?.error && (
          <div style={{ fontSize: 11, color: "#4a5568", textAlign: "center", padding: "12px 0" }}>
            No news available
          </div>
        )}

        {displayItems.map((item, i) => (
          <a
            key={i}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-lg px-3 py-2 transition-colors hover:bg-white/5"
            style={{ textDecoration: "none" }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#e0e8ff",
                lineHeight: "1.4",
                marginBottom: 2,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {item.title}
            </div>
            <div className="flex items-center gap-2">
              {item.source && (
                <span style={{ fontSize: 9, color: "#00d4ff" }}>
                  {item.source}
                </span>
              )}
              {item.published_date && (
                <span style={{ fontSize: 9, color: "#4a5568" }}>
                  {item.published_date}
                </span>
              )}
              <ExternalLink size={8} style={{ color: "#4a5568" }} />
            </div>
          </a>
        ))}

        {!loading && news?.count !== undefined && news.count > 0 && (
          <div style={{ fontSize: 9, color: "#4a5568", textAlign: "center", paddingTop: 4 }}>
            {news.count} sources
          </div>
        )}
      </div>
    </div>
  );
}
