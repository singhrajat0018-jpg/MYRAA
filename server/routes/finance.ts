// ============================================================================
// MYRAA Phase 26 — Financial Intelligence REST API Routes
// ============================================================================

import type { ServerContext } from "./types";
import {
  TechnicalAnalysisEngine,
  FundamentalAnalysisEngine,
  EventAnalysisEngine,
  MarketRegimeEngine,
  EvidenceMatrixEngine,
  SignalEngine,
  RiskEngine,
  ScenarioEngine,
  ThesisEngine,
  WatchlistEngine,
  HistoricalIntegrityEngine,
  FinancialScreener,
  MarketDataNormalizer,
  DEFAULT_SIGNAL_WEIGHTS,
  TIMEFRAME_HORIZON_MAP,
} from "../../src/finance";
import type {
  OHLCVBar, Timeframe, TimeHorizon, StrategyType,
  MarketSnapshot, FinancialMetrics, NewsItem, Catalyst,
  AssetIdentity, ScreenFilter, WatchlistItem, AlertRule,
  TradingThesis, RiskAssessment,
} from "../../src/finance/contracts";

// --- Engine singletons ---

const technicalEngine = new TechnicalAnalysisEngine();
const fundamentalEngine = new FundamentalAnalysisEngine();
const eventEngine = new EventAnalysisEngine();
const regimeEngine = new MarketRegimeEngine();
const evidenceEngine = new EvidenceMatrixEngine();
const signalEngine = new SignalEngine();
const riskEngine = new RiskEngine();
const scenarioEngine = new ScenarioEngine();
const thesisEngine = new ThesisEngine();
const watchlistEngine = new WatchlistEngine();
const historicalEngine = new HistoricalIntegrityEngine();
const screener = new FinancialScreener();
const normalizer = new MarketDataNormalizer();

// --- In-memory state ---

const watchlist: WatchlistItem[] = [];
const thesisHistory: TradingThesis[] = [];

// --- Route Registration ---

export function registerFinanceRoutes(app: any, ctx: ServerContext) {

  // --- Health ---

  app.get("/api/finance/health", (_req: any, res: any) => {
    res.json({
      status: "ok",
      phase: 26,
      engines: {
        technical: true,
        fundamental: true,
        events: true,
        regime: true,
        evidence: true,
        signal: true,
        risk: true,
        scenario: true,
        thesis: true,
        watchlist: true,
        historical: true,
        screening: true,
      },
      watchlistSize: watchlist.length,
      thesisCount: thesisHistory.length,
    });
  });

  // --- Technical Analysis ---

  app.post("/api/finance/technical", (req: any, res: any) => {
    try {
      const { bars, timeframe, symbol } = req.body;
      if (!bars || !Array.isArray(bars) || bars.length === 0) {
        return res.json({ error: "bars array required", status: "INVALID_INPUT" });
      }
      const tf: Timeframe = timeframe || "1d";
      const result = technicalEngine.analyze(bars, tf, symbol || "UNKNOWN");
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Technical analysis failed", status: "ERROR" });
    }
  });

  // --- Fundamental Analysis ---

  app.post("/api/finance/fundamental", (req: any, res: any) => {
    try {
      const { metrics, earnings, peers } = req.body;
      if (!metrics) {
        return res.json({ error: "metrics required", status: "INVALID_INPUT" });
      }
      const result = fundamentalEngine.analyze(metrics, earnings || [], peers);
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Fundamental analysis failed", status: "ERROR" });
    }
  });

  // --- Event Analysis ---

  app.post("/api/finance/events", (req: any, res: any) => {
    try {
      const { news, catalysts, assetId } = req.body;
      const result = eventEngine.analyze(news || [], catalysts || [], assetId || "");
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Event analysis failed", status: "ERROR" });
    }
  });

  // --- Market Regime ---

  app.post("/api/finance/regime", (req: any, res: any) => {
    try {
      const { indexTrend, volatility, breadth, volumeTrend, riskSentiment } = req.body;
      const result = regimeEngine.classifyRegime({
        indexTrend: indexTrend || "UNKNOWN",
        volatility: volatility || 0,
        breadth,
        volumeTrend: volumeTrend || "STABLE",
        riskSentiment: riskSentiment || "NEUTRAL",
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Regime classification failed", status: "ERROR" });
    }
  });

  // --- Evidence Matrix ---

  app.post("/api/finance/evidence", (req: any, res: any) => {
    try {
      const { technical, fundamental, events, macro, regime, sector, symbol, assetId } = req.body;
      const result = evidenceEngine.buildMatrix({
        technical, fundamental, events, macro, regime, sector,
        symbol: symbol || "UNKNOWN", assetId: assetId || "",
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Evidence matrix failed", status: "ERROR" });
    }
  });

  // --- Signal Generation ---

  app.post("/api/finance/signal", (req: any, res: any) => {
    try {
      const { technical, fundamental, events, macro, regime, weights, symbol, assetId, timeframe, strategy } = req.body;
      const result = signalEngine.generate({
        technical, fundamental, events, macro, regime,
        weights: weights || DEFAULT_SIGNAL_WEIGHTS,
        symbol: symbol || "UNKNOWN", assetId: assetId || "",
        timeframe: timeframe || "SWING",
        strategy: strategy || "TREND",
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Signal generation failed", status: "ERROR" });
    }
  });

  // --- Risk Assessment ---

  app.post("/api/finance/risk", (req: any, res: any) => {
    try {
      const { snapshot, technical, fundamental, events, portfolio, symbol, assetId } = req.body;
      if (!snapshot) {
        return res.json({ error: "snapshot required", status: "INVALID_INPUT" });
      }
      const result = riskEngine.assess({
        snapshot, technical, fundamental, events, portfolio,
        symbol: symbol || "UNKNOWN", assetId: assetId || "",
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Risk assessment failed", status: "ERROR" });
    }
  });

  // --- Scenario Analysis ---

  app.post("/api/finance/scenario", (req: any, res: any) => {
    try {
      const { thesis, technical, fundamental, currentPrice, symbol, assetId, timeframe } = req.body;
      if (!thesis || currentPrice === undefined) {
        return res.json({ error: "thesis and currentPrice required", status: "INVALID_INPUT" });
      }
      const result = scenarioEngine.generate({
        thesis, technical, fundamental, currentPrice,
        symbol: symbol || "UNKNOWN", assetId: assetId || "",
        timeframe: timeframe || "SWING",
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Scenario generation failed", status: "ERROR" });
    }
  });

  // --- Thesis ---

  app.post("/api/finance/thesis", (req: any, res: any) => {
    try {
      const { symbol, assetId, timeHorizon, technical, fundamental, events, macro, regime,
        evidenceMatrix, signal, scenarios, risk, currentPrice } = req.body;
      if (!symbol || !evidenceMatrix || !signal || !scenarios || !risk || !currentPrice) {
        return res.json({ error: "symbol, evidenceMatrix, signal, scenarios, risk, currentPrice required", status: "INVALID_INPUT" });
      }
      const result = thesisEngine.build({
        symbol, assetId: assetId || "", timeHorizon: timeHorizon || "SWING",
        technical, fundamental, events, macro, regime,
        evidenceMatrix, signal, scenarios, risk, currentPrice,
      });
      thesisHistory.push(result);
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Thesis build failed", status: "ERROR" });
    }
  });

  app.get("/api/finance/thesis/history", (_req: any, res: any) => {
    res.json(thesisHistory.slice(-50));
  });

  // --- Watchlist ---

  app.get("/api/finance/watchlist", (_req: any, res: any) => {
    res.json(watchlistEngine.prioritize(watchlist));
  });

  app.post("/api/finance/watchlist", (req: any, res: any) => {
    try {
      const { symbol, assetId, reason, strategy, catalysts, invalidationConditions, priority } = req.body;
      if (!symbol || !reason || !strategy) {
        return res.json({ error: "symbol, reason, strategy required", status: "INVALID_INPUT" });
      }
      const item = watchlistEngine.create({
        symbol, assetId: assetId || "", reason, strategy,
        catalysts, invalidationConditions, priority,
      });
      watchlist.push(item);
      res.json(item);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Watchlist add failed", status: "ERROR" });
    }
  });

  app.delete("/api/finance/watchlist/:symbol", (req: any, res: any) => {
    const idx = watchlist.findIndex(w => w.symbol === req.params.symbol);
    if (idx >= 0) {
      watchlist.splice(idx, 1);
      res.json({ success: true });
    } else {
      res.json({ error: "Symbol not found in watchlist", status: "NOT_FOUND" });
    }
  });

  // --- Screening ---

  app.post("/api/finance/screen", (req: any, res: any) => {
    try {
      const { universe, filters, marketData, technicals, fundamentals, limit } = req.body;
      if (!universe || !Array.isArray(universe)) {
        return res.json({ error: "universe array required", status: "INVALID_INPUT" });
      }
      const mdMap = new Map<string, MarketSnapshot>();
      if (marketData && typeof marketData === "object") {
        for (const [k, v] of Object.entries(marketData)) mdMap.set(k, v as MarketSnapshot);
      }
      const techMap = new Map();
      const fundMap = new Map();
      const results = screener.screen({
        universe, filters: filters || [], marketData: mdMap,
        technicals: techMap, fundamentals: fundMap, limit: limit || 20,
      });
      res.json(results);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Screening failed", status: "ERROR" });
    }
  });

  // --- Historical Integrity ---

  app.post("/api/finance/historical/lookahead", (req: any, res: any) => {
    try {
      const { analysisTimestamp, dataTimestamps, eventTimestamps } = req.body;
      const result = historicalEngine.validateLookAheadBias({
        analysisTimestamp: analysisTimestamp || new Date().toISOString(),
        dataTimestamps: dataTimestamps || [],
        eventTimestamps,
      });
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Look-ahead validation failed", status: "ERROR" });
    }
  });

  app.post("/api/finance/historical/integrity", (req: any, res: any) => {
    try {
      const { bars } = req.body;
      const result = historicalEngine.validateDataIntegrity(bars || []);
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Integrity check failed", status: "ERROR" });
    }
  });

  // --- Normalization ---

  app.post("/api/finance/normalize/symbol", (req: any, res: any) => {
    try {
      const { symbol, exchange } = req.body;
      const result = normalizer.normalizeSymbol(symbol || "", exchange);
      res.json({ normalized: result });
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "Normalization failed", status: "ERROR" });
    }
  });

  app.post("/api/finance/validate/ohlcv", (req: any, res: any) => {
    try {
      const { bar } = req.body;
      const result = normalizer.validateOHLCV(bar);
      res.json(result);
    } catch (err) {
      res.json({ error: err instanceof Error ? err.message : "OHLCV validation failed", status: "ERROR" });
    }
  });

}
