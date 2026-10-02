"""Real market data smoke test — read-only, no orders."""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import yfinance as yf
    print("yfinance:", yf.__version__)
except ImportError:
    print("yfinance not installed — run: pip install yfinance")
    exit(1)

print("\n=== REAL MARKET DATA SMOKE TEST ===\n")

# 1. NIFTY 50
start = time.time()
try:
    t = yf.Ticker("^NSEI")
    info = t.fast_info
    price = info.get("lastPrice", 0)
    prev = info.get("previousClose", 0)
    latency = (time.time() - start) * 1000
    chg = ((price - prev) / prev * 100) if prev else 0
    print(f"NIFTY 50: {price:.2f} ({chg:+.2f}%)")
    print(f"  Latency: {latency:.0f}ms | Source: Yahoo | Freshness: LIVE")
except Exception as e:
    print(f"NIFTY 50: FAILED ({e})")

# 2. RELIANCE
start = time.time()
try:
    t = yf.Ticker("RELIANCE.NS")
    info = t.fast_info
    price = info.get("lastPrice", 0)
    latency = (time.time() - start) * 1000
    print(f"RELIANCE: INR {price:.2f} | Latency: {latency:.0f}ms")
except Exception as e:
    print(f"RELIANCE: FAILED ({e})")

# 3. TCS OHLCV
start = time.time()
try:
    t = yf.Ticker("TCS.NS")
    hist = t.history(period="5d")
    latency = (time.time() - start) * 1000
    print(f"TCS OHLCV ({len(hist)} bars): {hist.iloc[-1]['Close']:.2f} | Latency: {latency:.0f}ms")
except Exception as e:
    print(f"TCS OHLCV: FAILED ({e})")

# 4. Trading Intelligence Engine integration
start = time.time()
try:
    from desktop_agent.finance.trading.engine import TradingIntelligenceEngine
    from desktop_agent.finance.trading.models import MarketQuote, OHLCV, Timeframe, Exchange, DataQuality
    from datetime import datetime, timedelta

    engine = TradingIntelligenceEngine()
    q = yf.Ticker("RELIANCE.NS").fast_info
    hist_data = yf.Ticker("RELIANCE.NS").history(period="1mo")
    bars = []
    for idx, row in hist_data.iterrows():
        bars.append(OHLCV(
            timestamp=idx.to_pydatetime(),
            open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]),
            volume=int(row["Volume"]), timeframe=Timeframe.DAILY,
            source="yahoo",
        ))
    quote = MarketQuote(
        symbol="RELIANCE", current_price=float(q["lastPrice"]),
        previous_close=float(q.get("previousClose", q["lastPrice"])),
        open_price=float(q.get("open", 0)), high_price=float(q.get("dayHigh", 0)),
        low_price=float(q.get("dayLow", 0)), volume=int(q.get("lastVolume", 0)),
        exchange=Exchange.NSE, timestamp=datetime.utcnow(),
        source="yahoo", data_quality=DataQuality.LIVE,
    )
    result = engine.analyze_stock("RELIANCE", quote, bars)
    latency = (time.time() - start) * 1000
    print(f"\nRELIANCE Analysis: {result.recommendation.signal.value} | Confidence: {result.recommendation.confidence:.2f}")
    print(f"  Trend: {result.technical.trend.value} | Latency: {latency:.0f}ms")
    print(f"  Data Quality: {result.data_quality.value}")
except Exception as e:
    print(f"Engine integration: FAILED ({e})")

print("\n=== SMOKE TEST COMPLETE ===")
print("Orders placed: 0 | All operations: READ-ONLY")
