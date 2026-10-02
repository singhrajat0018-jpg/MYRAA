// ============================================================================
// MYRAA Phase 26 — Financial Domain Contracts
// ============================================================================

// --- Asset Model ---

export type AssetType =
  | 'STOCK' | 'ETF' | 'INDEX' | 'FOREX' | 'COMMODITY'
  | 'CRYPTO' | 'FUTURE' | 'OPTION_REFERENCE' | 'OTHER';

export type Exchange =
  | 'NSE' | 'BSE' | 'NYSE' | 'NASDAQ' | 'LSE' | 'TSE'
  | 'HKEX' | 'SSE' | 'SZSE' | 'KRX' | 'ASX' | 'TSX'
  | 'CRYPTO_BINANCE' | 'CRYPTO_COINBASE' | 'FOREX'
  | 'COMEX' | 'CBOT' | 'NYMEX' | 'OTHER';

export type Currency = 'INR' | 'USD' | 'EUR' | 'GBP' | 'JPY' | 'AUD' | 'CAD' | 'CHF' | 'CNY' | 'OTHER';

export type MarketStatus = 'PRE_MARKET' | 'REGULAR' | 'AFTER_HOURS' | 'CLOSED' | 'HALT' | 'UNKNOWN';

export type DataQuality = 'COMPLETE' | 'PARTIAL' | 'SPARSE' | 'UNKNOWN';

export type Freshness = 'REALTIME' | 'NEAR_REALTIME' | 'DELAYED' | 'END_OF_DAY' | 'HISTORICAL' | 'STALE' | 'UNAVAILABLE';

export type DataSourceMode = 'REALTIME' | 'NEAR_REALTIME' | 'DELAYED' | 'END_OF_DAY' | 'HISTORICAL' | 'ON_DEMAND';

export type DataAdjustment = 'RAW' | 'ADJUSTED';

export interface AssetIdentity {
  readonly assetId: string;
  readonly symbol: string;
  readonly exchange: Exchange;
  readonly assetType: AssetType;
  readonly currency: Currency;
  readonly country: string;
  readonly sector?: string;
  readonly industry?: string;
  readonly name?: string;
  readonly isin?: string;
  readonly providerIds: readonly string[];
  readonly aliases: readonly string[];
  readonly status: 'ACTIVE' | 'DELISTED' | 'SUSPENDED' | 'UNKNOWN';
  readonly metadata: Record<string, unknown>;
}

// --- OHLCV ---

export interface OHLCVBar {
  readonly timestamp: string;
  readonly open: number;
  readonly high: number;
  readonly low: number;
  readonly close: number;
  readonly volume: number;
  readonly adjustment: DataAdjustment;
  readonly source: string;
}

// --- Market Snapshot ---

export interface MarketSnapshot {
  readonly assetId: string;
  readonly symbol: string;
  readonly price: number;
  readonly open: number;
  readonly high: number;
  readonly low: number;
  readonly close: number;
  readonly previousClose: number;
  readonly volume: number;
  readonly change: number;
  readonly changePercent: number;
  readonly timestamp: string;
  readonly source: string;
  readonly freshness: Freshness;
  readonly confidence: number;
  readonly marketStatus: MarketStatus;
  readonly currency: Currency;
  readonly dayHigh: number;
  readonly dayLow: number;
  readonly fiftyTwoWeekHigh?: number;
  readonly fiftyTwoWeekLow?: number;
  readonly marketCap?: number;
  readonly pe?: number;
  readonly eps?: number;
  readonly dividendYield?: number;
}

// --- Technical Analysis ---

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d' | '1w' | '1M';

export type TrendDirection = 'UPTREND' | 'DOWNTREND' | 'RANGE' | 'TRANSITION' | 'UNKNOWN';

export type SignalBias = 'LONG_BIAS' | 'SHORT_BIAS' | 'NEUTRAL' | 'WATCH' | 'NO_SIGNAL';

export interface SMA { readonly value: number; readonly period: number; }
export interface EMA { readonly value: number; readonly period: number; }
export interface RSI { readonly value: number; readonly period: number; }
export interface MACDData { readonly macd: number; readonly signal: number; readonly histogram: number; }
export interface BollingerBands { readonly upper: number; readonly middle: number; readonly lower: number; readonly bandwidth: number; }
export interface ATR { readonly value: number; readonly period: number; }
export interface VWAP { readonly value: number; }
export interface ADX { readonly value: number; readonly plusDI: number; readonly minusDI: number; }

export interface TechnicalIndicators {
  readonly sma20?: SMA;
  readonly sma50?: SMA;
  readonly sma100?: SMA;
  readonly sma200?: SMA;
  readonly ema9?: EMA;
  readonly ema21?: EMA;
  readonly ema50?: EMA;
  readonly rsi14?: RSI;
  readonly macd?: MACDData;
  readonly bollinger?: BollingerBands;
  readonly atr14?: ATR;
  readonly adx14?: ADX;
  readonly vwap?: VWAP;
  readonly roc12?: number;
  readonly momentum10?: number;
  readonly obv?: number;
  readonly volumeRatio?: number;
  readonly relativeVolume?: number;
}

export interface SupportResistanceLevel {
  readonly price: number;
  readonly type: 'SUPPORT' | 'RESISTANCE';
  readonly strength: number;
  readonly source: 'SWING' | 'VOLUME' | 'MOVING_AVERAGE' | 'PIVOT' | 'ROUND_NUMBER';
  readonly timeframe: Timeframe;
  readonly touchCount: number;
}

export interface TrendAnalysis {
  readonly direction: TrendDirection;
  readonly strength: number;
  readonly duration: number;
  readonly evidence: readonly string[];
  readonly movingAverageAlignment: 'BULLISH' | 'BEARISH' | 'MIXED';
  readonly priceVsSMA200: 'ABOVE' | 'BELOW' | 'AT';
}

export interface BreakoutSignal {
  readonly type: 'BREAKOUT' | 'BREAKDOWN' | 'FALSE_BREAKOUT' | 'RETEST';
  readonly level: number;
  readonly confirmationRequired: boolean;
  readonly volumeConfirmation: boolean;
  readonly confidence: number;
}

export interface VolumeAnalysis {
  readonly currentVolume: number;
  readonly averageVolume20d: number;
  readonly relativeVolume: number;
  readonly trend: 'EXPANDING' | 'CONTRACTING' | 'STABLE';
  readonly significance: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface VolatilityAnalysis {
  readonly atr14: number;
  readonly historicalVolatility20d: number;
  readonly historicalVolatility60d: number;
  readonly regime: 'HIGH' | 'NORMAL' | 'LOW';
  readonly percentileRank: number;
}

export interface MultiTimeframeAlignment {
  readonly monthly: TrendDirection;
  readonly weekly: TrendDirection;
  readonly daily: TrendDirection;
  readonly fourHour: TrendDirection;
  readonly oneHour: TrendDirection;
  readonly alignmentScore: number;
  readonly description: string;
}

export interface TechnicalAnalysis {
  readonly assetId: string;
  readonly symbol: string;
  readonly timeframe: Timeframe;
  readonly timestamp: string;
  readonly indicators: TechnicalIndicators;
  readonly trend: TrendAnalysis;
  readonly supportResistance: readonly SupportResistanceLevel[];
  readonly breakout: BreakoutSignal | null;
  readonly volume: VolumeAnalysis;
  readonly volatility: VolatilityAnalysis;
  readonly multiTimeframe: MultiTimeframeAlignment;
  readonly signal: SignalBias;
  readonly signalStrength: number;
  readonly bullishEvidence: readonly string[];
  readonly bearishEvidence: readonly string[];
  readonly neutralEvidence: readonly string[];
}

// --- Fundamental Analysis ---

export type FiscalPeriod = 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'FY' | 'TTM';

export interface FinancialMetrics {
  readonly revenue?: number;
  readonly revenueGrowthYoy?: number;
  readonly revenueGrowthQoQ?: number;
  readonly netIncome?: number;
  readonly eps?: number;
  readonly epsSurprise?: number;
  readonly grossMargin?: number;
  readonly operatingMargin?: number;
  readonly netMargin?: number;
  readonly freeCashFlow?: number;
  readonly operatingCashFlow?: number;
  readonly totalDebt?: number;
  readonly totalCash?: number;
  readonly debtToEquity?: number;
  readonly currentRatio?: number;
  readonly roe?: number;
  readonly roic?: number;
  readonly pe?: number;
  readonly forwardPE?: number;
  readonly ps?: number;
  readonly pb?: number;
  readonly evToEbitda?: number;
  readonly dividendYield?: number;
  readonly beta?: number;
  readonly marketCap?: number;
  readonly enterpriseValue?: number;
  readonly period: FiscalPeriod;
  readonly fiscalYear: number;
  readonly fiscalQuarter?: number;
  readonly reportDate: string;
  readonly currency: Currency;
  readonly source: string;
  readonly freshness: Freshness;
}

export interface EarningsEvent {
  readonly assetId: string;
  readonly symbol: string;
  readonly date: string;
  readonly time: 'BEFORE_MARKET' | 'AFTER_MARKET' | 'DURING_MARKET' | 'UNKNOWN';
  readonly epsEstimate?: number;
  readonly epsActual?: number;
  readonly revenueEstimate?: number;
  readonly revenueActual?: number;
  readonly epsSurprisePercent?: number;
  readonly revenueSurprisePercent?: number;
  readonly guidance?: string;
  readonly postEarningsMove?: number;
  readonly source: string;
  readonly freshness: Freshness;
}

export interface FundamentalAnalysis {
  readonly assetId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly metrics: FinancialMetrics;
  readonly earnings: readonly EarningsEvent[];
  readonly valuationAssessment: 'UNDERVALUED' | 'FAIR' | 'OVERVALUED' | 'UNKNOWN';
  readonly growthAssessment: 'HIGH_GROWTH' | 'MODERATE_GROWTH' | 'LOW_GROWTH' | 'DECLINE' | 'UNKNOWN';
  readonly financialHealth: 'STRONG' | 'ADEQUATE' | 'WEAK' | 'CRITICAL' | 'UNKNOWN';
  readonly qualityScore: number;
  readonly peerComparison?: PeerComparison;
  readonly dataQuality: DataQuality;
  readonly evidence: readonly string[];
}

export interface PeerComparison {
  readonly peers: readonly string[];
  readonly peRank?: number;
  readonly growthRank?: number;
  readonly marginRank?: number;
  readonly healthRank?: number;
}

// --- News & Events ---

export type EventType =
  | 'EARNINGS' | 'GUIDANCE' | 'MERGER' | 'ACQUISITION' | 'PRODUCT'
  | 'REGULATION' | 'LAWSUIT' | 'MANAGEMENT' | 'ANALYST' | 'MACRO'
  | 'GEOPOLITICAL' | 'SUPPLY_CHAIN' | 'CAPITAL_ALLOCATION' | 'DIVIDEND'
  | 'BUYBACK' | 'INSIDER_TRADING' | 'RATING_CHANGE' | 'PRICE_TARGET'
  | 'SEC_FILING' | 'IPO' | 'DELISTING' | 'OTHER';

export type EventImpact = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'UNCERTAIN';

export type SentimentLabel = 'VERY_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'VERY_BEARISH';

export interface NewsItem {
  readonly id: string;
  readonly title: string;
  readonly summary: string;
  readonly source: string;
  readonly url?: string;
  readonly publishedAt: string;
  readonly retrievedAt: string;
  readonly assetIds: readonly string[];
  readonly eventType: EventType;
  readonly sentiment: SentimentLabel;
  readonly sentimentScore: number;
  readonly importance: 'HIGH' | 'MEDIUM' | 'LOW';
  readonly freshness: Freshness;
  readonly reliability: number;
  readonly clusteringId?: string;
}

export interface EventAnalysis {
  readonly assetId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly recentNews: readonly NewsItem[];
  readonly upcomingCatalysts: readonly Catalyst[];
  readonly eventClassification: EventType;
  readonly overallSentiment: SentimentLabel;
  readonly sentimentScore: number;
  readonly newsFreshness: Freshness;
  readonly contradictionDetected: boolean;
  readonly evidence: readonly string[];
}

export interface Catalyst {
  readonly id: string;
  readonly type: EventType;
  readonly description: string;
  readonly expectedDate?: string;
  readonly knownTime: boolean;
  readonly directionHypothesis: 'POSITIVE' | 'NEGATIVE' | 'UNCERTAIN';
  readonly importance: 'HIGH' | 'MEDIUM' | 'LOW';
  readonly confidence: number;
  readonly status: 'UPCOMING' | 'PASSED' | 'EXPIRED';
  readonly evidence: readonly string[];
}

// --- Market Regime ---

export type RegimeType =
  | 'TRENDING_BULL' | 'TRENDING_BEAR' | 'RANGE'
  | 'HIGH_VOLATILITY' | 'LOW_VOLATILITY'
  | 'RISK_ON' | 'RISK_OFF' | 'MIXED' | 'UNKNOWN';

export interface MarketRegime {
  readonly type: RegimeType;
  readonly confidence: number;
  readonly evidence: readonly string[];
  readonly indexTrend: TrendDirection;
  readonly volatilityRegime: 'HIGH' | 'NORMAL' | 'LOW';
  readonly breadthIndicator?: number;
  readonly timestamp: string;
  readonly source: string;
}

export interface SectorAnalysis {
  readonly sector: string;
  readonly relativeStrength: number;
  readonly performance1d: number;
  readonly performance1w: number;
  readonly performance1m: number;
  readonly trend: TrendDirection;
  readonly topMovers: readonly { symbol: string; change: number }[];
  readonly rotationSignal: 'ROTATING_IN' | 'ROTATING_OUT' | 'NEUTRAL';
  readonly evidence: readonly string[];
}

export interface MacroContext {
  readonly inflationTrend?: 'RISING' | 'FALLING' | 'STABLE';
  readonly rateEnvironment?: 'HAWKISH' | 'DOVISH' | 'NEUTRAL';
  readonly gdpGrowth?: number;
  readonly employmentTrend?: 'IMPROVING' | 'WEAKENING' | 'STABLE';
  readonly riskSentiment: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
  readonly usdStrength?: 'STRONG' | 'WEAK' | 'NEUTRAL';
  readonly oilTrend?: 'RISING' | 'FALLING' | 'STABLE';
  readonly timestamp: string;
  readonly source: string;
  readonly evidence: readonly string[];
}

// --- Evidence Matrix ---

export type EvidenceCategory = 'TECHNICAL' | 'FUNDAMENTAL' | 'EVENT' | 'MACRO' | 'SENTIMENT' | 'REGIME' | 'SECTOR' | 'CROSS_ASSET';

export interface EvidenceEntry {
  readonly id: string;
  readonly category: EvidenceCategory;
  readonly claim: string;
  readonly direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  readonly support: number;
  readonly contradiction: number;
  readonly freshness: Freshness;
  readonly sourceQuality: number;
  readonly confidence: number;
  readonly source: string;
  readonly timestamp: string;
}

export interface EvidenceMatrix {
  readonly assetId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly entries: readonly EvidenceEntry[];
  readonly bullishCount: number;
  readonly bearishCount: number;
  readonly neutralCount: number;
  readonly contradictions: readonly { claim1: string; claim2: string; reason: string }[];
  readonly overallDirection: SignalBias;
  readonly confidence: number;
  readonly dataQuality: DataQuality;
}

// --- Signal Engine ---

export interface SignalComponents {
  readonly technicalScore: number;
  readonly fundamentalScore: number;
  readonly eventScore: number;
  readonly macroScore: number;
  readonly sentimentScore: number;
  readonly regimeScore: number;
  readonly riskScore: number;
}

export interface SignalWeights {
  readonly technical: number;
  readonly fundamental: number;
  readonly event: number;
  readonly macro: number;
  readonly sentiment: number;
  readonly regime: number;
}

export interface TradingSignal {
  readonly id: string;
  readonly assetId: string;
  readonly symbol: string;
  readonly bias: SignalBias;
  readonly strength: number;
  readonly confidence: number;
  readonly components: SignalComponents;
  readonly weights: SignalWeights;
  readonly timeframe: TimeHorizon;
  readonly strategy: StrategyType;
  readonly evidence: readonly string[];
  readonly contradictions: readonly string[];
  readonly invalidationConditions: readonly string[];
  readonly createdAt: string;
  readonly expiresAt: string;
  readonly status: 'ACTIVE' | 'EXPIRED' | 'INVALIDATED' | 'SUPERSEDED';
  readonly version: number;
}

// --- Risk Engine ---

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME' | 'UNKNOWN';

export interface RiskAssessment {
  readonly assetId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly overallRisk: RiskLevel;
  readonly volatilityRisk: RiskLevel;
  readonly liquidityRisk: RiskLevel;
  readonly eventRisk: RiskLevel;
  readonly drawdownRisk: RiskLevel;
  readonly correlationRisk: RiskLevel;
  readonly dataRisk: RiskLevel;
  readonly gapRisk: RiskLevel;
  readonly evidence: readonly string[];
  readonly maxDrawdownScenario?: number;
  readonly stopLossGuidance?: number;
  readonly positionSizingGuidance?: string;
  readonly riskRewardRatio?: number;
}

// --- Scenario Engine ---

export type ScenarioType = 'BULL' | 'BASE' | 'BEAR' | 'STRESS';

export interface ScenarioVariable {
  readonly name: string;
  readonly description: string;
  readonly bullValue?: number | string;
  readonly baseValue?: number | string;
  readonly bearValue?: number | string;
  readonly stressValue?: number | string;
}

export interface Scenario {
  readonly type: ScenarioType;
  readonly description: string;
  readonly assumptions: readonly string[];
  readonly expectedImplications: readonly string[];
  readonly risks: readonly string[];
  readonly confidence: number;
  readonly probabilityType: 'QUANTIFIED' | 'QUALITATIVE';
  readonly probability?: number;
  readonly priceTarget?: number;
  readonly timeframe: string;
}

export interface ScenarioAnalysis {
  readonly assetId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly scenarios: readonly Scenario[];
  readonly variables: readonly ScenarioVariable[];
  readonly sensitivityAnalysis: readonly { variable: string; impact: string }[];
  readonly timeframe: TimeHorizon;
}

// --- Trading Thesis ---

export type TimeHorizon = 'INTRADAY' | 'SHORT_TERM' | 'SWING' | 'MEDIUM_TERM' | 'LONG_TERM';

export type ThesisStatus = 'ACTIVE' | 'STALE' | 'INVALIDATED' | 'REASSESS_REQUIRED' | 'RESOLVED' | 'EXPIRED';

export interface TradingThesis {
  readonly id: string;
  readonly version: number;
  readonly assetId: string;
  readonly symbol: string;
  readonly timeHorizon: TimeHorizon;
  readonly marketContext: string;
  readonly technicalContext: string;
  readonly fundamentalContext: string;
  readonly eventContext: string;
  readonly macroContext: string;
  readonly bullCase: string;
  readonly bearCase: string;
  readonly baseCase: string;
  readonly keyRisks: readonly string[];
  readonly keyCatalysts: readonly string[];
  readonly invalidationConditions: readonly string[];
  readonly confidence: number;
  readonly signalBias: SignalBias;
  readonly signalStrength: number;
  readonly evidence: readonly EvidenceEntry[];
  readonly scenarios: readonly Scenario[];
  readonly riskAssessment: RiskAssessment;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly expiresAt?: string;
  readonly status: ThesisStatus;
  readonly parentId?: string;
  readonly auditTrail: readonly ThesisAuditEntry[];
}

export interface ThesisAuditEntry {
  readonly timestamp: string;
  readonly action: 'CREATED' | 'UPDATED' | 'INVALIDATED' | 'REASSESS_REQUIRED' | 'SUPERSEDED';
  readonly reason: string;
  readonly previousVersion?: number;
}

// --- Watchlist ---

export interface WatchlistItem {
  readonly assetId: string;
  readonly symbol: string;
  readonly name?: string;
  readonly reason: string;
  readonly strategy: StrategyType;
  readonly thesis?: string;
  readonly catalysts: readonly Catalyst[];
  readonly invalidationConditions: readonly string[];
  readonly alertRules: readonly AlertRule[];
  readonly createdAt: string;
  readonly lastReviewedAt?: string;
  readonly priority: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface AlertRule {
  readonly type: 'PRICE_ABOVE' | 'PRICE_BELOW' | 'VOLUME_SPIKE' | 'NEWS_EVENT' | 'TECHNICAL_LEVEL' | 'THESIS_INVALIDATION';
  readonly threshold?: number;
  readonly enabled: boolean;
  readonly message: string;
}

// --- Screening ---

export type StrategyType = 'MOMENTUM' | 'TREND' | 'MEAN_REVERSION' | 'BREAKOUT' | 'EVENT_DRIVEN' | 'VALUE' | 'GROWTH' | 'QUALITY' | 'RELATIVE_STRENGTH' | 'MACRO';

export interface ScreenFilter {
  readonly field: string;
  readonly operator: 'GT' | 'LT' | 'EQ' | 'GTE' | 'LTE' | 'BETWEEN' | 'IN' | 'CONTAINS';
  readonly value: number | string | readonly (number | string)[];
}

export interface ScreenResult {
  readonly assetId: string;
  readonly symbol: string;
  readonly name?: string;
  readonly score: number;
  readonly matchedFilters: readonly string[];
  readonly signal: SignalBias;
  readonly risk: RiskLevel;
  readonly catalyst?: Catalyst;
  readonly evidence: readonly string[];
}

// --- Trade Idea (Analytical Only) ---

export type TradeIdeaStatus = 'DRAFT' | 'ACTIVE' | 'TRIGGERED' | 'EXPIRED' | 'INVALIDATED' | 'COMPLETED';

export interface TradeIdea {
  readonly id: string;
  readonly assetId: string;
  readonly symbol: string;
  readonly direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  readonly timeHorizon: TimeHorizon;
  readonly setup: string;
  readonly entryConcept?: string;
  readonly riskZone?: number;
  readonly targetConcept?: string;
  readonly invalidation: string;
  readonly catalyst?: string;
  readonly evidence: readonly EvidenceEntry[];
  readonly riskAssessment: RiskAssessment;
  readonly confidence: number;
  readonly status: TradeIdeaStatus;
  readonly createdAt: string;
  readonly expiresAt?: string;
  readonly thesisId?: string;
}

// --- Order Intent (Future Boundary) ---

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP_LOSS' | 'STOP_LIMIT';

export interface OrderIntent {
  readonly symbol: string;
  readonly side: OrderSide;
  readonly orderType: OrderType;
  readonly quantity: number;
  readonly limitPrice?: number;
  readonly stopPrice?: string;
  readonly timeInForce: 'DAY' | 'GTC' | 'IOC';
  readonly thesisId?: string;
  readonly signalId?: string;
  readonly note?: string;
}

// --- Portfolio Context ---

export interface PortfolioPosition {
  readonly symbol: string;
  readonly quantity: number;
  readonly avgPrice: number;
  readonly currentPrice: number;
  readonly unrealizedPnL: number;
  readonly unrealizedPnLPercent: number;
  readonly weight: number;
  readonly sector?: string;
  readonly country?: string;
}

export interface PortfolioContext {
  readonly positions: readonly PortfolioPosition[];
  readonly totalValue: number;
  readonly cashAvailable?: number;
  readonly sectorAllocation: readonly { sector: string; weight: number }[];
  readonly concentrationRisk: RiskLevel;
  readonly currencyExposure: readonly { currency: string; weight: number }[];
}

// --- Evaluation ---

export interface ForecastEvaluation {
  readonly thesisId: string;
  readonly symbol: string;
  readonly originalBias: SignalBias;
  readonly originalConfidence: number;
  readonly originalTimestamp: string;
  readonly evaluationTimestamp: string;
  readonly actualDirection: 'UP' | 'DOWN' | 'FLAT';
  readonly actualMovePercent: number;
  readonly correctDirection: boolean;
  readonly confidenceWasCalibrated: boolean;
  readonly notes: string;
}

// --- Financial Analysis Result ---

export interface FinancialAnalysisResult {
  readonly analysisId: string;
  readonly symbol: string;
  readonly assetId: string;
  readonly timestamp: string;
  readonly timeHorizon: TimeHorizon;
  readonly currentPrice: MarketSnapshot;
  readonly technical: TechnicalAnalysis;
  readonly fundamental?: FundamentalAnalysis;
  readonly events: EventAnalysis;
  readonly macro: MacroContext;
  readonly marketRegime: MarketRegime;
  readonly sectors: readonly SectorAnalysis[];
  readonly evidenceMatrix: EvidenceMatrix;
  readonly signal: TradingSignal;
  readonly scenarios: ScenarioAnalysis;
  readonly risk: RiskAssessment;
  readonly thesis: TradingThesis;
  readonly catalysts: readonly Catalyst[];
  readonly invalidationConditions: readonly string[];
  readonly dataQuality: DataQuality;
  readonly sources: readonly string[];
  readonly freshness: Freshness;
  readonly explanation: string;
}

// --- Constants ---

export const DEFAULT_SIGNAL_WEIGHTS: SignalWeights = {
  technical: 0.30,
  fundamental: 0.25,
  event: 0.15,
  macro: 0.10,
  sentiment: 0.10,
  regime: 0.10,
};

export const TIMEFRAME_HORIZON_MAP: Record<Timeframe, TimeHorizon> = {
  '1m': 'INTRADAY',
  '5m': 'INTRADAY',
  '15m': 'INTRADAY',
  '1h': 'SHORT_TERM',
  '4h': 'SWING',
  '1d': 'SWING',
  '1w': 'MEDIUM_TERM',
  '1M': 'LONG_TERM',
};

export const FRESHNESS_MAX_AGE_MS: Record<Freshness, number> = {
  REALTIME: 30_000,
  NEAR_REALTIME: 60_000,
  DELAYED: 300_000,
  END_OF_DAY: 86_400_000,
  HISTORICAL: Infinity,
  STALE: Infinity,
  UNAVAILABLE: 0,
};

export const RISK_SCORE_MAP: Record<RiskLevel, number> = {
  LOW: 0.2,
  MEDIUM: 0.5,
  HIGH: 0.75,
  EXTREME: 0.95,
  UNKNOWN: 0.5,
};

export const ASSET_TYPE_CURRENCIES: Record<AssetType, Currency> = {
  STOCK: 'USD',
  ETF: 'USD',
  INDEX: 'USD',
  FOREX: 'USD',
  COMMODITY: 'USD',
  CRYPTO: 'USD',
  FUTURE: 'USD',
  OPTION_REFERENCE: 'USD',
  OTHER: 'USD',
};

export const HIGH_IMPACT_EVENT_TYPES: readonly EventType[] = [
  'EARNINGS', 'GUIDANCE', 'MERGER', 'ACQUISITION', 'REGULATION',
  'RATING_CHANGE', 'SEC_FILING', 'IPO',
];
