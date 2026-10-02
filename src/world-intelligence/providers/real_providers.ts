// ============================================================================
// MYRAA World Intelligence — Real Provider Implementations
// Free, verified providers for live world data ingestion
// ============================================================================

import type { RawWorldData, RawWorldItem } from '../contracts';
import type { IngestionProvider } from '../ingestion';

// ============================================================================
// Helper: Safe HTTP fetch with timeout and size limit
// ============================================================================

async function safeFetch(url: string, timeoutMs = 10_000, maxBytes = 2_000_000): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal, headers: { 'User-Agent': 'MYRAA/1.0' } });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const text = await res.text();
    if (text.length > maxBytes) throw new Error(`Response too large: ${text.length} bytes`);
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

// ============================================================================
// Open-Meteo Weather (FREE, no auth)
// ============================================================================

export class OpenMeteoWeatherProvider implements IngestionProvider {
  readonly id = 'open-meteo-weather';
  readonly name = 'Open-Meteo Weather';
  readonly category = 'weather';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;
  private cities: { name: string; country: string; lat: number; lon: number }[];

  constructor(cities?: { name: string; country: string; lat: number; lon: number }[]) {
    this.cities = cities || [
      { name: 'New Delhi', country: 'IN', lat: 28.6139, lon: 77.2090 },
      { name: 'Mumbai', country: 'IN', lat: 19.0760, lon: 72.8777 },
      { name: 'New York', country: 'US', lat: 40.7128, lon: -74.0060 },
      { name: 'London', country: 'GB', lat: 51.5074, lon: -0.1278 },
      { name: 'Tokyo', country: 'JP', lat: 35.6762, lon: 139.6503 },
    ];
  }

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    for (const city of this.cities) {
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${city.lat}&longitude=${city.lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto`;
        const data = await safeFetch(url) as Record<string, unknown>;
        const current = data.current as Record<string, unknown>;
        if (current) {
          items.push({
            type: 'entity' as const,
            raw: {
              city: city.name,
              country: city.country,
              temperature: current.temperature_2m,
              humidity: current.relative_humidity_2m,
              wind_speed: current.wind_speed_10m,
              weather_code: current.weather_code,
              time: current.time,
              category: 'weather',
            },
            title: `Weather in ${city.name}: ${current.temperature_2m}°C`,
            summary: `Temperature: ${current.temperature_2m}°C, Humidity: ${current.relative_humidity_2m}%, Wind: ${current.wind_speed_10m} km/h`,
            entities: [city.name, city.country],
            publishedAt: String(current.time || new Date().toISOString()),
          });
        }
      } catch {
        // Skip failed cities, continue with others
      }
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// GNews (FREE tier, no auth for basic)
// ============================================================================

export class GNewsProvider implements IngestionProvider {
  readonly id = 'gnews';
  readonly name = 'GNews';
  readonly category = 'news';
  readonly sourceClass = 'SECONDARY' as const;
  readonly enabled = true;
  private apiKey?: string;
  private topics: string[];

  constructor(apiKey?: string, topics?: string[]) {
    this.apiKey = apiKey;
    this.topics = topics || ['world', 'technology', 'business', 'science'];
  }

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    for (const topic of this.topics) {
      try {
        const baseUrl = this.apiKey
          ? `https://gnews.io/api/v4/top-headlines?topic=${topic}&lang=en&max=10&apikey=${this.apiKey}`
          : `https://gnews.io/api/v4/top-headlines?topic=${topic}&lang=en&max=10&apikey=demo`;
        const data = await safeFetch(baseUrl) as Record<string, unknown>;
        const articles = (data.articles || []) as Record<string, unknown>[];
        for (const article of articles) {
          items.push({
            type: 'event' as const,
            raw: {
              ...article,
              category: topic,
              source_name: (article.source as Record<string, unknown>)?.name,
              source_url: (article.source as Record<string, unknown>)?.url,
            },
            title: String(article.title || ''),
            summary: String(article.description || ''),
            entities: this.extractEntitiesFromText(String(article.title || '') + ' ' + String(article.description || '')),
            sourceUrl: String(article.url || ''),
            publishedAt: String(article.publishedAt || article.published_at || ''),
          });
        }
      } catch {
        // Skip failed topics
      }
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }

  private extractEntitiesFromText(text: string): string[] {
    const entities: string[] = [];
    const knownEntities = [
      'Apple', 'Google', 'Microsoft', 'Amazon', 'NVIDIA', 'Tesla', 'OpenAI', 'Meta',
      'Bitcoin', 'Ethereum', 'NIFTY', 'Sensex', 'Dow Jones', 'S&P 500',
      'NASA', 'WHO', 'UN', 'EU', 'IMF', 'World Bank',
      'India', 'China', 'USA', 'UK', 'Japan', 'Germany', 'France',
      'Elon Musk', 'Sam Altman', 'Sundar Pichai', 'Tim Cook', 'Satya Nadella',
    ];
    for (const entity of knownEntities) {
      if (text.toLowerCase().includes(entity.toLowerCase())) {
        entities.push(entity);
      }
    }
    return entities;
  }
}

// ============================================================================
// NewsData.io (FREE tier, 200 req/day)
// ============================================================================

export class NewsDataProvider implements IngestionProvider {
  readonly id = 'newsdata';
  readonly name = 'NewsData.io';
  readonly category = 'news';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;
  private apiKey?: string;
  private categories: string[];

  constructor(apiKey?: string, categories?: string[]) {
    this.apiKey = apiKey;
    this.categories = categories || ['technology', 'business', 'science', 'environment'];
  }

  async fetch(): Promise<RawWorldData> {
    if (!this.apiKey) {
      return { providerId: this.id, retrievedAt: new Date().toISOString(), items: [] };
    }
    const items: RawWorldItem[] = [];
    for (const category of this.categories) {
      try {
        const url = `https://newsdata.io/api/1/latest?apikey=${this.apiKey}&category=${category}&language=en&size=10`;
        const data = await safeFetch(url) as Record<string, unknown>;
        const results = (data.results || []) as Record<string, unknown>[];
        for (const article of results) {
          items.push({
            type: 'event' as const,
            raw: { ...article, category },
            title: String(article.title || ''),
            summary: String(article.description || article.content || ''),
            entities: this.extractEntities(article),
            sourceUrl: String(article.link || ''),
            publishedAt: String(article.pubDate || ''),
          });
        }
      } catch {
        // Skip failed categories
      }
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }

  private extractEntities(article: Record<string, unknown>): string[] {
    const entities: string[] = [];
    if (article.creator && Array.isArray(article.creator)) {
      for (const c of article.creator) entities.push(String(c));
    }
    if (article.source_id) entities.push(String(article.source_id));
    if (article.keywords && Array.isArray(article.keywords)) {
      for (const kw of article.keywords) entities.push(String(kw));
    }
    return entities;
  }
}

// ============================================================================
// Wikipedia (FREE, no auth)
// ============================================================================

export class WikipediaProvider implements IngestionProvider {
  readonly id = 'wikipedia';
  readonly name = 'Wikipedia';
  readonly category = 'knowledge';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;
  private topics: string[];

  constructor(topics?: string[]) {
    this.topics = topics || ['Artificial intelligence', 'Climate change', 'Space exploration'];
  }

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    for (const topic of this.topics) {
      try {
        const searchUrl = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(topic)}`;
        const data = await safeFetch(searchUrl) as Record<string, unknown>;
        if (data.title) {
          items.push({
            type: 'entity' as const,
            raw: {
              ...data,
              category: 'knowledge',
              page_id: data.pageid,
              extract: data.extract,
            },
            title: String(data.title || topic),
            summary: String(data.extract || data.description || ''),
            entities: [String(data.title || topic)],
            sourceUrl: String((data as any).content_urls?.desktop?.page || ''),
          });
        }
      } catch {
        // Skip failed topics
      }
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// GitHub Trending (FREE, no auth)
// ============================================================================

export class GitHubTrendingProvider implements IngestionProvider {
  readonly id = 'github-trending';
  readonly name = 'GitHub Trending';
  readonly category = 'technology';
  readonly sourceClass = 'SECONDARY' as const;
  readonly enabled = true;
  private languages: string[];

  constructor(languages?: string[]) {
    this.languages = languages || ['python', 'typescript', 'javascript'];
  }

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    // Use GitHub search API for trending repos (created in last week)
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    for (const lang of this.languages) {
      try {
        const url = `https://api.github.com/search/repositories?q=language:${lang}+created:>${weekAgo}&sort=stars&order=desc&per_page=5`;
        const data = await safeFetch(url) as Record<string, unknown>;
        const repos = (data.items || []) as Record<string, unknown>[];
        for (const repo of repos) {
          const owner = repo.owner as Record<string, unknown>;
          items.push({
            type: 'event' as const,
            raw: {
              ...repo,
              category: 'technology',
              language: lang,
              owner_name: owner?.login,
            },
            title: `${repo.full_name}: ${repo.description || 'New trending repository'}`,
            summary: `${repo.description || ''} - ${repo.stargazers_count} stars, ${repo.language}`,
            entities: [String(owner?.login || ''), String(repo.name || ''), lang],
            sourceUrl: String(repo.html_url || ''),
            publishedAt: String(repo.created_at || ''),
          });
        }
      } catch {
        // Skip failed languages
      }
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// Exchange Rates (FREE, no auth)
// ============================================================================

export class ExchangeRatesProvider implements IngestionProvider {
  readonly id = 'exchange-rates';
  readonly name = 'Exchange Rates';
  readonly category = 'finance';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;
  private baseCurrency: string;
  private targetCurrencies: string[];

  constructor(baseCurrency = 'USD', targets?: string[]) {
    this.baseCurrency = baseCurrency;
    this.targetCurrencies = targets || ['INR', 'EUR', 'GBP', 'JPY', 'CNY'];
  }

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    try {
      const url = `https://open.er-api.com/v6/latest/${this.baseCurrency}`;
      const data = await safeFetch(url) as Record<string, unknown>;
      const rates = data.rates as Record<string, number>;
      if (rates) {
        for (const currency of this.targetCurrencies) {
          if (rates[currency]) {
            items.push({
              type: 'entity' as const,
              raw: {
                category: 'finance',
                base: this.baseCurrency,
                target: currency,
                rate: rates[currency],
                time: data.time_last_update_utc,
              },
              title: `${this.baseCurrency}/${currency}: ${rates[currency]}`,
              summary: `1 ${this.baseCurrency} = ${rates[currency]} ${currency}`,
              entities: [this.baseCurrency, currency],
              publishedAt: String(data.time_last_update_utc || new Date().toISOString()),
            });
          }
        }
      }
    } catch {
      // Provider failed
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// NASA APOD (FREE, no auth for demo)
// ============================================================================

export class NasaApodProvider implements IngestionProvider {
  readonly id = 'nasa-apod';
  readonly name = 'NASA Astronomy Picture of the Day';
  readonly category = 'astronomy';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    try {
      const url = `https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY`;
      const data = await safeFetch(url) as Record<string, unknown>;
      if (data.title) {
        items.push({
          type: 'event' as const,
          raw: { ...data, category: 'astronomy' },
          title: String(data.title),
          summary: String(data.explanation || ''),
          entities: ['NASA', 'Astronomy'],
          sourceUrl: String(data.url || ''),
          publishedAt: String(data.date ? `${data.date}T00:00:00Z` : new Date().toISOString()),
        });
      }
    } catch {
      // Provider failed
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// Open Notify — ISS Location (FREE, no auth)
// ============================================================================

export class IssLocationProvider implements IngestionProvider {
  readonly id = 'iss-location';
  readonly name = 'ISS Location';
  readonly category = 'space';
  readonly sourceClass = 'PRIMARY' as const;
  readonly enabled = true;

  async fetch(): Promise<RawWorldData> {
    const items: RawWorldItem[] = [];
    try {
      const data = await safeFetch('http://api.open-notify.org/iss-now.json') as Record<string, unknown>;
      if (data.iss_position) {
        const pos = data.iss_position as Record<string, string>;
        items.push({
          type: 'entity' as const,
          raw: {
            category: 'space',
            latitude: parseFloat(pos.latitude),
            longitude: parseFloat(pos.longitude),
            timestamp: data.timestamp,
          },
          title: `ISS Location: ${pos.latitude}°, ${pos.longitude}°`,
          summary: `International Space Station at latitude ${pos.latitude}, longitude ${pos.longitude}`,
          entities: ['ISS', 'International Space Station', 'NASA'],
          publishedAt: new Date((data.timestamp as number) * 1000).toISOString(),
        });
      }
    } catch {
      // Provider failed
    }
    return { providerId: this.id, retrievedAt: new Date().toISOString(), items };
  }
}

// ============================================================================
// Provider Factory
// ============================================================================

export function createDefaultProviders(): IngestionProvider[] {
  return [
    new OpenMeteoWeatherProvider(),
    new WikipediaProvider(['Artificial_intelligence', 'Climate_change', 'Space_exploration', 'Indian_economy']),
    new GitHubTrendingProvider(['python', 'typescript']),
    new ExchangeRatesProvider('USD', ['INR', 'EUR', 'GBP', 'JPY']),
    new NasaApodProvider(),
    new IssLocationProvider(),
  ];
}

export function createNewsProviders(apiKeys?: { gnews?: string; newsdata?: string }): IngestionProvider[] {
  const providers: IngestionProvider[] = [];
  if (apiKeys?.gnews || !apiKeys) {
    providers.push(new GNewsProvider(apiKeys?.gnews));
  }
  if (apiKeys?.newsdata) {
    providers.push(new NewsDataProvider(apiKeys.newsdata));
  }
  return providers;
}
