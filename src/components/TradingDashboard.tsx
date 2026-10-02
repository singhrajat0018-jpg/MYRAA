import { useState, useEffect, useCallback } from 'react'

const API = ''

interface PortfolioSnapshot {
  positions: Array<{
    symbol: string; quantity: number; average_price: number; current_price: number
    previous_close: number; unrealized_pnl: number; day_change_percent: number
    holding_duration_days: number; sector: string
  }>
  cash: number; total_invested: number; total_market_value: number
  total_unrealized_pnl: number; total_pnl_percent: number; total_day_pnl: number
  position_count: number; timestamp: string
}

interface PositionAdvice {
  symbol: string; sector: string; quantity: number; avg_price: number
  current_price: number; invested_value: number; market_value: number
  unrealized_pnl: number; unrealized_pnl_pct: number; day_pnl: number
  action: string; confidence: number; reasoning: string; risk_level: string
  target: number; stop_loss: number
}

interface PortfolioAdvice {
  overall_assessment: string; portfolio_health: string; total_invested: number
  total_value: number; total_pnl: number; total_pnl_pct: number; day_pnl: number
  cash_available: number; position_advices: PositionAdvice[]
  sector_exposure: Record<string, number>; concentration_warnings: string[]
  risk_warnings: string[]; next_actions: string[]; timestamp: string
}

interface StockGuidance {
  symbol: string; recommendation: string; confidence: number
  current_price: number; target_price: number; stop_loss: number
  risk_reward: string; technical_view: string; portfolio_impact: string
  reasoning_hinglish: string; key_levels: Record<string, number>
}

interface Alert {
  alert_id: string; alert_type: string; symbol: string; message: string
  severity: string; timestamp: string; acknowledged: boolean
}

interface HealthState {
  groww: { connected: boolean; last_sync: string | null; portfolio_positions: number }
  alerts: { rules_count: number; alerts_fired: number; unacknowledged: number }
  scheduler: { running: boolean; last_run: string | null; run_count: number }
  engine: { engine: string; broker_connected: boolean; active_theses: number }
}

const pnl = (v: number) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400'
const pnlB = (v: number) => v > 0 ? 'bg-emerald-500/10 border-emerald-500/20' : v < 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-white/5 border-white/10'
const badge = (m: Record<string, string>, k: string) => m[k] || 'bg-white/10 text-gray-300'
const HEALTH: Record<string, string> = { STRONG: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30', MODERATE: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30', WEAK: 'bg-orange-500/20 text-orange-300 border-orange-500/30', CRITICAL: 'bg-red-500/20 text-red-300 border-red-500/30' }
const ACTION: Record<string, string> = { HOLD: 'bg-blue-500/20 text-blue-300', ADD: 'bg-emerald-500/20 text-emerald-300', REDUCE: 'bg-orange-500/20 text-orange-300', EXIT: 'bg-red-500/20 text-red-300', WAIT: 'bg-gray-500/20 text-gray-300' }
const SEVERITY: Record<string, string> = { INFO: 'bg-blue-500/20 text-blue-300', WARNING: 'bg-orange-500/20 text-orange-300', CRITICAL: 'bg-red-500/20 text-red-300' }
const INR = (v: number) => `₹${(v || 0).toLocaleString('en-IN')}`

export default function TradingDashboard({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<'portfolio' | 'analysis' | 'alerts' | 'health'>('portfolio')
  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null)
  const [advice, setAdvice] = useState<PortfolioAdvice | null>(null)
  const [stockInput, setStockInput] = useState('')
  const [stockGuidance, setStockGuidance] = useState<StockGuidance | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [health, setHealth] = useState<HealthState | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dataStatus, setDataStatus] = useState<'LIVE' | 'UNAVAILABLE'>('UNAVAILABLE')

  const fetchAll = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [pRes, aRes, alRes, hRes] = await Promise.all([
        fetch(`/api/groww/portfolio`).catch(() => null),
        fetch(`/api/groww/analyze`).catch(() => null),
        fetch(`/api/trading/alerts?limit=30`).catch(() => null),
        fetch(`/api/trading/health`).catch(() => null),
      ])
      if (pRes?.ok) { const d = await pRes.json(); setPortfolio(d.snapshot); setDataStatus(d.connected ? 'LIVE' : 'UNAVAILABLE') }
      if (aRes?.ok) setAdvice(await aRes.json())
      if (alRes?.ok) setAlerts((await alRes.json()).alerts || [])
      if (hRes?.ok) setHealth(await hRes.json())
    } catch { setError('Failed to load data') }
    setLoading(false)
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const fetchStock = async () => {
    if (!stockInput.trim()) return
    setLoading(true)
      try { const r = await fetch(`/api/groww/stock/${stockInput.toUpperCase()}`); if (r.ok) setStockGuidance(await r.json()) }
    catch { setError('Failed') }
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-6xl h-[90vh] bg-black/60 border border-white/10 rounded-2xl backdrop-blur-xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <h1 className="text-lg font-display font-semibold text-white">MYRAA Trading Advisor</h1>
            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${dataStatus === 'LIVE' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-red-500/20 text-red-300 border-red-500/30'}`}>
              {dataStatus === 'LIVE' ? 'LIVE GROWW' : 'DISCONNECTED'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchAll} className="text-xs text-gray-400 hover:text-white px-3 py-1 rounded-lg bg-white/5 border border-white/10" disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-white text-xl ml-2">✕</button>
          </div>
        </div>

        <div className="flex gap-1 px-6 py-2 border-b border-white/5">
          {(['portfolio', 'analysis', 'alerts', 'health'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2 text-red-300 text-sm">{error}</div>}

          {tab === 'portfolio' && (<>
            {portfolio && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <div className="text-xs text-gray-400 mb-1">Total Value</div>
                  <div className="text-xl font-mono text-white">{INR(portfolio.total_market_value)}</div>
                </div>
                <div className={`border rounded-xl p-4 ${pnlB(portfolio.total_day_pnl)}`}>
                  <div className="text-xs text-gray-400 mb-1">Day P&L</div>
                  <div className={`text-xl font-mono ${pnl(portfolio.total_day_pnl)}`}>
                    {portfolio.total_day_pnl >= 0 ? '+' : ''}{INR(portfolio.total_day_pnl)}
                  </div>
                </div>
                <div className={`border rounded-xl p-4 ${pnlB(portfolio.total_unrealized_pnl)}`}>
                  <div className="text-xs text-gray-400 mb-1">Total P&L</div>
                  <div className={`text-xl font-mono ${pnl(portfolio.total_pnl_percent)}`}>
                    {portfolio.total_pnl_percent >= 0 ? '+' : ''}{portfolio.total_pnl_percent.toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <div className="text-xs text-gray-400 mb-1">Cash</div>
                  <div className="text-xl font-mono text-white">{INR(portfolio.cash)}</div>
                </div>
              </div>
            )}

            {advice && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="flex items-center gap-3 mb-3">
                  <span className={`text-xs px-3 py-1 rounded-full border ${badge(HEALTH, advice.portfolio_health)}`}>{advice.portfolio_health}</span>
                  <span className="text-white text-sm font-medium">{advice.overall_assessment}</span>
                </div>
                {advice.concentration_warnings.length > 0 && (
                  <div className="space-y-1 mb-3">
                    {advice.concentration_warnings.map((w, i) => (
                      <div key={i} className="text-xs text-orange-300 bg-orange-500/10 rounded-lg px-3 py-1">{w}</div>
                    ))}
                  </div>
                )}
                {advice.risk_warnings.length > 0 && (
                  <div className="space-y-1 mb-3">
                    {advice.risk_warnings.map((w, i) => (
                      <div key={i} className="text-xs text-red-300 bg-red-500/10 rounded-lg px-3 py-1">{w}</div>
                    ))}
                  </div>
                )}
                {advice.next_actions.length > 0 && (
                  <div className="space-y-1">
                    {advice.next_actions.map((a, i) => (
                      <div key={i} className="text-xs text-blue-300 bg-blue-500/10 rounded-lg px-3 py-1">{a}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {advice?.position_advices && advice.position_advices.length > 0 && (
              <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b border-white/5 text-xs text-gray-400 font-medium">POSITIONS</div>
                <div className="divide-y divide-white/5">
                  {advice.position_advices.map(pa => (
                    <div key={pa.symbol} className="px-5 py-3 flex items-center gap-4">
                      <div className="w-20">
                        <div className="text-sm font-medium text-white">{pa.symbol}</div>
                        <div className="text-[10px] text-gray-400">{pa.sector}</div>
                      </div>
                      <div className="text-right w-16">
                        <div className="text-xs text-gray-400">Qty</div>
                        <div className="text-sm text-white font-mono">{pa.quantity}</div>
                      </div>
                      <div className="text-right w-20">
                        <div className="text-xs text-gray-400">Avg</div>
                        <div className="text-sm text-white font-mono">{INR(pa.avg_price)}</div>
                      </div>
                      <div className="text-right w-20">
                        <div className="text-xs text-gray-400">LTP</div>
                        <div className="text-sm text-white font-mono">{INR(pa.current_price)}</div>
                      </div>
                      <div className="text-right w-24">
                        <div className="text-xs text-gray-400">P&L</div>
                        <div className={`text-sm font-mono ${pnl(pa.unrealized_pnl_pct)}`}>{pa.unrealized_pnl_pct >= 0 ? '+' : ''}{pa.unrealized_pnl_pct.toFixed(1)}%</div>
                      </div>
                      <div className="text-right w-20">
                        <div className="text-xs text-gray-400">Day</div>
                        <div className={`text-sm font-mono ${pnl(pa.day_pnl)}`}>{pa.day_pnl >= 0 ? '+' : ''}{INR(pa.day_pnl)}</div>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${badge(ACTION, pa.action)}`}>{pa.action}</span>
                      <div className="text-[10px] text-gray-400 flex-1 text-right">{pa.reasoning}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {advice?.sector_exposure && Object.keys(advice.sector_exposure).length > 0 && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="text-xs text-gray-400 font-medium mb-3">SECTOR EXPOSURE</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(advice.sector_exposure).map(([s, pct]) => (
                    <div key={s} className="bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                      <div className="text-xs text-gray-400">{s}</div>
                      <div className="text-sm text-white font-mono">{pct.toFixed(1)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>)}

          {tab === 'analysis' && (<>
            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <div className="text-xs text-gray-400 font-medium mb-3">STOCK GUIDANCE</div>
              <div className="flex gap-2">
                <input value={stockInput} onChange={e => setStockInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && fetchStock()}
                  placeholder="Enter symbol (e.g., RELIANCE)"
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-white/20" />
                <button onClick={fetchStock} disabled={loading}
                  className="px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-sm text-white hover:bg-white/20 transition-colors disabled:opacity-50">
                  Analyze
                </button>
              </div>
            </div>
            {stockGuidance && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-display font-semibold text-white">{stockGuidance.symbol}</span>
                  <span className={`text-xs px-3 py-1 rounded-full ${badge(ACTION, stockGuidance.recommendation)}`}>{stockGuidance.recommendation}</span>
                  <span className="text-xs text-gray-400">Confidence: {(stockGuidance.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-white/5 rounded-lg p-3"><div className="text-[10px] text-gray-400">Current</div><div className="text-sm text-white font-mono">{INR(stockGuidance.current_price)}</div></div>
                  <div className="bg-emerald-500/10 rounded-lg p-3"><div className="text-[10px] text-gray-400">Target</div><div className="text-sm text-emerald-400 font-mono">{INR(stockGuidance.target_price)}</div></div>
                  <div className="bg-red-500/10 rounded-lg p-3"><div className="text-[10px] text-gray-400">Stop Loss</div><div className="text-sm text-red-400 font-mono">{INR(stockGuidance.stop_loss)}</div></div>
                  <div className="bg-white/5 rounded-lg p-3"><div className="text-[10px] text-gray-400">R:R</div><div className="text-sm text-white font-mono">{stockGuidance.risk_reward}</div></div>
                </div>
                <div className="text-sm text-gray-300">{stockGuidance.technical_view}</div>
                <div className="text-xs text-gray-400">{stockGuidance.portfolio_impact}</div>
                {stockGuidance.key_levels && Object.keys(stockGuidance.key_levels).length > 0 && (
                  <div className="flex gap-2">
                    {Object.entries(stockGuidance.key_levels).map(([k, v]) => (
                      <div key={k} className="bg-white/5 rounded-lg px-3 py-1"><span className="text-[10px] text-gray-400">{k}: </span><span className="text-xs text-white font-mono">{INR(v)}</span></div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>)}

          {tab === 'alerts' && (<>
            {alerts.length === 0 ? (
              <div className="bg-white/5 border border-white/10 rounded-xl p-8 text-center text-gray-400 text-sm">No alerts yet. Configure rules to get started.</div>
            ) : (
              <div className="space-y-2">
                {alerts.map(a => (
                  <div key={a.alert_id} className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${a.acknowledged ? 'bg-white/5 border-white/5 opacity-50' : 'bg-white/5 border-white/10'}`}>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${badge(SEVERITY, a.severity)}`}>{a.severity}</span>
                    {a.symbol && <span className="text-xs text-white font-medium w-20">{a.symbol}</span>}
                    <span className="text-sm text-gray-300 flex-1">{a.message}</span>
                    <span className="text-[10px] text-gray-500">{new Date(a.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            )}
          </>)}

          {tab === 'health' && health && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="text-xs text-gray-400 font-medium mb-3">GROWW</div>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Connected</span><span className={`text-sm ${health.groww.connected ? 'text-emerald-400' : 'text-red-400'}`}>{health.groww.connected ? 'Yes' : 'No'}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Positions</span><span className="text-sm text-white">{health.groww.portfolio_positions}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Last Sync</span><span className="text-sm text-white">{health.groww.last_sync ? new Date(health.groww.last_sync).toLocaleString() : 'Never'}</span></div>
                </div>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="text-xs text-gray-400 font-medium mb-3">ENGINE</div>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Engine</span><span className="text-sm text-white">{health.engine.engine}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Active Theses</span><span className="text-sm text-white">{health.engine.active_theses}</span></div>
                </div>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="text-xs text-gray-400 font-medium mb-3">ALERTS</div>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Rules</span><span className="text-sm text-white">{health.alerts.rules_count}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Fired</span><span className="text-sm text-white">{health.alerts.alerts_fired}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Unacknowledged</span><span className="text-sm text-orange-400">{health.alerts.unacknowledged}</span></div>
                </div>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="text-xs text-gray-400 font-medium mb-3">SCHEDULER</div>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Running</span><span className={`text-sm ${health.scheduler.running ? 'text-emerald-400' : 'text-gray-400'}`}>{health.scheduler.running ? 'Yes' : 'No'}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Run Count</span><span className="text-sm text-white">{health.scheduler.run_count}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-gray-400">Last Run</span><span className="text-sm text-white">{health.scheduler.last_run ? new Date(health.scheduler.last_run).toLocaleString() : 'Never'}</span></div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
