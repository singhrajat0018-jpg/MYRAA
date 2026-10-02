import type {
  MarketRegime,
  RegimeType,
  TrendDirection,
  SectorAnalysis,
  MacroContext,
  StrategyType,
} from './contracts';

export interface RegimeClassifyInput {
  readonly indexTrend: TrendDirection;
  readonly volatility: number;
  readonly breadth?: number;
  readonly volumeTrend: 'EXPANDING' | 'CONTRACTING' | 'STABLE';
  readonly riskSentiment: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
}

export class MarketRegimeEngine {
  private readonly source = 'MarketRegimeEngine';

  classifyRegime(data: RegimeClassifyInput): MarketRegime {
    const { indexTrend, volatility, breadth, volumeTrend, riskSentiment } = data;
    const evidence: string[] = [];
    let type: RegimeType;
    let confidence = 0;

    if (indexTrend === 'UPTREND') {
      type = 'TRENDING_BULL'; confidence += 0.3;
      evidence.push('Index is in uptrend');
    } else if (indexTrend === 'DOWNTREND') {
      type = 'TRENDING_BEAR'; confidence += 0.3;
      evidence.push('Index is in downtrend');
    } else if (indexTrend === 'RANGE') {
      type = 'RANGE'; confidence += 0.25;
      evidence.push('Index is range-bound');
    } else {
      type = 'MIXED';
      evidence.push('Index trend is transitioning or unknown');
    }

    if (volatility > 0.25) {
      if (type === 'TRENDING_BULL' || type === 'TRENDING_BEAR') {
        type = 'HIGH_VOLATILITY';
        evidence.push('High volatility overrides directional regime');
      }
      confidence += 0.15;
    } else if (volatility < 0.08) {
      confidence += 0.1;
      evidence.push('Low volatility environment');
    }

    if (breadth !== undefined) {
      if (type === 'TRENDING_BULL' && breadth > 0.6) {
        confidence += 0.15;
        evidence.push(`Strong breadth (${breadth.toFixed(2)}) confirms bull trend`);
      } else if (type === 'TRENDING_BEAR' && breadth < 0.4) {
        confidence += 0.15;
        evidence.push(`Weak breadth (${breadth.toFixed(2)}) confirms bear trend`);
      } else if (breadth > 0.4 && breadth < 0.6) {
        confidence += 0.05;
        evidence.push(`Neutral breadth (${breadth.toFixed(2)})`);
      }
    }

    if (volumeTrend === 'EXPANDING') {
      confidence += 0.1;
      evidence.push('Volume is expanding — directional conviction');
    } else if (volumeTrend === 'CONTRACTING') {
      confidence -= 0.05;
      evidence.push('Volume is contracting — potential trend exhaustion');
    }

    if (riskSentiment === 'RISK_ON' && type === 'TRENDING_BULL') {
      confidence += 0.1;
      evidence.push('Risk-on sentiment aligns with bull trend');
    } else if (riskSentiment === 'RISK_OFF' && type === 'TRENDING_BEAR') {
      confidence += 0.1;
      evidence.push('Risk-off sentiment aligns with bear trend');
    } else if (riskSentiment !== 'NEUTRAL') {
      evidence.push(`Risk sentiment (${riskSentiment}) does not align with trend`);
    }

    if (riskSentiment === 'RISK_OFF' && type !== 'TRENDING_BEAR' && type !== 'HIGH_VOLATILITY') {
      type = 'RISK_OFF';
      evidence.push('Risk-off sentiment dominates');
    } else if (riskSentiment === 'RISK_ON' && type === 'RANGE') {
      type = 'RISK_ON';
      evidence.push('Risk-on sentiment in range environment');
    }

    return {
      type,
      confidence: Math.max(0.1, Math.min(1.0, confidence)),
      evidence,
      indexTrend,
      volatilityRegime: this.classifyVolatility(volatility * 100, volatility * 80, volatility > 0.2 ? 80 : 30),
      breadthIndicator: breadth,
      timestamp: new Date().toISOString(),
      source: this.source,
    };
  }

  classifyVolatility(atr: number, historicalVol: number, percentileRank: number): 'HIGH' | 'NORMAL' | 'LOW' {
    let score = 0;
    if (atr > 3.0) score += 2;
    else if (atr > 1.5) score += 1;
    if (historicalVol > 30) score += 2;
    else if (historicalVol > 15) score += 1;
    if (percentileRank > 80) score += 2;
    else if (percentileRank > 60) score += 1;
    else if (percentileRank < 20) score -= 1;
    if (score >= 4) return 'HIGH';
    if (score <= 0) return 'LOW';
    return 'NORMAL';
  }

  analyzeSectors(
    sectorData: readonly {
      sector: string;
      performance1d: number;
      performance1w: number;
      performance1m: number;
      stocks: readonly string[];
    }[],
  ): readonly SectorAnalysis[] {
    if (sectorData.length === 0) return [];
    const avg1m = sectorData.reduce((s, d) => s + d.performance1m, 0) / sectorData.length;

    return sectorData.map((d) => {
      const relativeStrength = d.performance1m - avg1m;

      let trend: TrendDirection;
      if (d.performance1w > 0 && d.performance1m > 0) trend = 'UPTREND';
      else if (d.performance1w < 0 && d.performance1m < 0) trend = 'DOWNTREND';
      else if (Math.abs(d.performance1m) < 1) trend = 'RANGE';
      else trend = 'TRANSITION';

      const topMovers = d.stocks.slice(0, 5).map((symbol) => ({
        symbol,
        change: d.performance1d * (0.8 + (symbol.charCodeAt(0) % 5) * 0.1),
      }));

      const evidence: string[] = [];
      if (relativeStrength > 2) evidence.push(`${d.sector} outperforming peers`);
      else if (relativeStrength < -2) evidence.push(`${d.sector} underperforming peers`);

      let rotationSignal: 'ROTATING_IN' | 'ROTATING_OUT' | 'NEUTRAL';
      if (d.performance1w > 1 && d.performance1m > 2) {
        rotationSignal = 'ROTATING_IN';
        evidence.push(`Money flowing into ${d.sector}`);
      } else if (d.performance1w < -1 && d.performance1m < -2) {
        rotationSignal = 'ROTATING_OUT';
        evidence.push(`Money flowing out of ${d.sector}`);
      } else {
        rotationSignal = 'NEUTRAL';
      }

      return {
        sector: d.sector, relativeStrength,
        performance1d: d.performance1d, performance1w: d.performance1w, performance1m: d.performance1m,
        trend, topMovers, rotationSignal, evidence,
      };
    });
  }

  detectRotation(
    sectors: readonly SectorAnalysis[],
  ): readonly { from: string; to: string; signal: 'ROTATING_IN' | 'ROTATING_OUT' }[] {
    if (sectors.length < 2) return [];
    const results: { from: string; to: string; signal: 'ROTATING_IN' | 'ROTATING_OUT' }[] = [];

    const rotatingIn = sectors.filter((s) => s.rotationSignal === 'ROTATING_IN');
    const rotatingOut = sectors.filter((s) => s.rotationSignal === 'ROTATING_OUT');

    for (const out of rotatingOut) {
      for (const inS of rotatingIn) {
        results.push({ from: out.sector, to: inS.sector, signal: 'ROTATING_IN' });
      }
    }

    if (results.length === 0) {
      const sorted = [...sectors].sort((a, b) => b.relativeStrength - a.relativeStrength);
      const third = Math.max(1, Math.floor(sorted.length / 3));
      const strong = sorted.slice(0, third);
      const weak = sorted.slice(-third);
      for (const w of weak) {
        for (const s of strong) {
          if (w.sector !== s.sector && w.relativeStrength < -1 && s.relativeStrength > 1) {
            results.push({ from: w.sector, to: s.sector, signal: 'ROTATING_IN' });
          }
        }
      }
    }
    return results;
  }

  buildMacroContext(data: {
    inflationTrend?: string;
    rateEnvironment?: string;
    gdpGrowth?: number;
    employmentTrend?: string;
    usdStrength?: string;
    oilTrend?: string;
  }): MacroContext {
    const evidence: string[] = [];
    const inflationTrend = this.parseEnum(data.inflationTrend, ['RISING', 'FALLING', 'STABLE'] as const);
    const rateEnvironment = this.parseEnum(data.rateEnvironment, ['HAWKISH', 'DOVISH', 'NEUTRAL'] as const);
    const employmentTrend = this.parseEnum(data.employmentTrend, ['IMPROVING', 'WEAKENING', 'STABLE'] as const);
    const usdStrength = this.parseEnum(data.usdStrength, ['STRONG', 'WEAK', 'NEUTRAL'] as const);
    const oilTrend = this.parseEnum(data.oilTrend, ['RISING', 'FALLING', 'STABLE'] as const);

    let riskScore = 0;
    if (inflationTrend === 'FALLING') { riskScore += 1; evidence.push('Falling inflation is risk-positive'); }
    else if (inflationTrend === 'RISING') { riskScore -= 1; evidence.push('Rising inflation is risk-negative'); }
    if (rateEnvironment === 'DOVISH') { riskScore += 1; evidence.push('Dovish rates support risk assets'); }
    else if (rateEnvironment === 'HAWKISH') { riskScore -= 1; evidence.push('Hawkish rates pressure risk assets'); }
    if (data.gdpGrowth !== undefined) {
      if (data.gdpGrowth > 3) { riskScore += 1; evidence.push(`Strong GDP growth (${data.gdpGrowth}%)`); }
      else if (data.gdpGrowth < 0) { riskScore -= 1; evidence.push(`Negative GDP growth (${data.gdpGrowth}%)`); }
    }
    if (employmentTrend === 'IMPROVING') { riskScore += 1; evidence.push('Employment improving'); }
    else if (employmentTrend === 'WEAKENING') { riskScore -= 1; evidence.push('Employment weakening'); }
    if (usdStrength === 'STRONG') { riskScore -= 0.5; evidence.push('Strong USD is mildly risk-negative'); }
    else if (usdStrength === 'WEAK') { riskScore += 0.5; evidence.push('Weak USD is mildly risk-positive'); }
    if (oilTrend === 'RISING') { riskScore -= 0.5; evidence.push('Rising oil costs weigh on margins'); }
    else if (oilTrend === 'FALLING') { riskScore += 0.5; evidence.push('Falling oil supports consumer spending'); }

    let riskSentiment: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
    if (riskScore >= 2) riskSentiment = 'RISK_ON';
    else if (riskScore <= -2) riskSentiment = 'RISK_OFF';
    else riskSentiment = 'NEUTRAL';
    if (evidence.length === 0) evidence.push('Limited macro data available');

    return {
      inflationTrend, rateEnvironment, gdpGrowth: data.gdpGrowth,
      employmentTrend, riskSentiment, usdStrength, oilTrend,
      timestamp: new Date().toISOString(), source: this.source, evidence,
    };
  }

  assessRegimeCompatibility(
    strategy: StrategyType, regime: RegimeType,
  ): { compatible: boolean; confidence: number; reason: string } {
    const matrix: Record<StrategyType, RegimeType[]> = {
      MOMENTUM: ['TRENDING_BULL', 'TRENDING_BEAR', 'RISK_ON'],
      TREND: ['TRENDING_BULL', 'TRENDING_BEAR'],
      MEAN_REVERSION: ['RANGE', 'LOW_VOLATILITY'],
      BREAKOUT: ['RANGE', 'TRENDING_BULL', 'TRENDING_BEAR'],
      EVENT_DRIVEN: ['TRENDING_BULL', 'TRENDING_BEAR', 'RANGE', 'MIXED'],
      VALUE: ['TRENDING_BEAR', 'RANGE', 'RISK_OFF'],
      GROWTH: ['TRENDING_BULL', 'RISK_ON', 'LOW_VOLATILITY'],
      QUALITY: ['TRENDING_BEAR', 'RISK_OFF', 'HIGH_VOLATILITY'],
      RELATIVE_STRENGTH: ['TRENDING_BULL', 'RISK_ON'],
      MACRO: ['RISK_ON', 'RISK_OFF', 'TRENDING_BULL', 'TRENDING_BEAR'],
    };

    if (matrix[strategy]?.includes(regime)) {
      return { compatible: true, confidence: 0.8, reason: `${strategy} is well-suited for ${regime}` };
    }
    if (regime === 'MIXED' || regime === 'UNKNOWN') {
      return { compatible: true, confidence: 0.4, reason: `${regime} regime — ${strategy} may work with elevated uncertainty` };
    }
    if ((strategy === 'MEAN_REVERSION' || strategy === 'VALUE') && regime === 'RISK_OFF') {
      return { compatible: true, confidence: 0.5, reason: `${strategy} can find opportunities in ${regime} but timing is difficult` };
    }
    return { compatible: false, confidence: 0.3, reason: `${strategy} is historically weak in ${regime} — consider waiting or adapting` };
  }

  private parseEnum<T extends string>(value: string | undefined, valid: readonly T[]): T | undefined {
    if (value === undefined) return undefined;
    return valid.find((v) => v === value.toUpperCase().trim()) as T | undefined;
  }
}
