import React from 'react';
import { motion } from 'motion/react';
import { 
  TrendingUp, 
  Target, 
  ShieldAlert, 
  ArrowUpRight, 
  ArrowDownRight,
  Activity,
  ChevronDown,
  Info,
  BadgeAlert
} from 'lucide-react';
import { actionLabel, cn, cnStockChange, formatPrice, formatPct, readableActionText, stageLabel, strategyLabel } from '../lib/utils';
import { MOCK_EVALUATION } from '../mock/data';
import { StockFocus, MainlineSector, StrategySignalCandidate, LianbanCandidate } from '../types';
import { api } from '../api/client';

export default function OverviewView() {
  const [data, setData] = React.useState(MOCK_EVALUATION);
  const [isLive, setIsLive] = React.useState(false);

  React.useEffect(() => {
    api.evaluation()
      .then((payload) => {
        setData(payload);
        setIsLive(true);
      })
      .catch(() => {
        setIsLive(false);
      });
  }, []);

  return (
    <div className="space-y-8">
      {/* Top Section: Market Reality & Mainlines */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <MarketRiskCard risk={data.market_risk} />
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4">
          {data.mainline_top5.map((sector, idx) => (
            <MainlineSectorCard key={idx} sector={sector} />
          ))}
        </div>
      </div>

      {/* Main Content: Focus Pool */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Target className="w-6 h-6 text-accent-orange" />
            <h3 className="text-xl font-bold tracking-tight">交易重点池 <span className="text-slate-500 font-normal ml-2">Top Focus</span></h3>
            <div className="flex items-center gap-2 px-2 py-0.5 bg-accent-orange/10 border border-accent-orange/20 rounded text-[10px] text-accent-orange font-mono uppercase">
              {isLive ? 'Live API' : 'Mock Fallback'}
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
             <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent-green" />
                <span>Grade A</span>
             </div>
             <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent-orange" />
                <span>Grade B</span>
             </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {data.focus_pool.map((stock) => (
            <StockFocusCard key={stock.symbol} stock={stock} />
          ))}
          {data.focus_pool.length === 0 && (
            <div className="glass-panel p-8 text-center text-slate-500 italic text-sm">
              今日暂无 A/B 重点池信号，查看下方完整观察池和阶段拦截。
            </div>
          )}
        </div>
      </div>


      <StrategySignalPool signals={data.strategy_signal_pool || []} />

      <LianbanPool candidates={data.lianban_pool || []} />

      {/* Secondary Pools */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <section className="space-y-4">
           <div className="flex items-center gap-2 text-accent-red">
              <ShieldAlert className="w-5 h-5" />
              <h4 className="font-bold uppercase tracking-wider text-sm">卖出预警 Warning</h4>
           </div>
           <div className="space-y-3">
              {data.sell_signals.map((signal, i) => (
                <div key={i} className="glass-panel p-4 border-l-4 border-l-accent-red flex items-center justify-between group hover:bg-accent-red/5 transition-colors">
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="font-bold text-lg">{signal.name}</span>
                      <span className="text-xs text-slate-500 font-mono">{signal.symbol}</span>
                    </div>
                    <p className="text-sm text-accent-red mt-1">{signal.reason}</p>
                  </div>
                  <div className="text-right">
                    <span className="px-3 py-1 bg-accent-red text-white text-xs font-bold rounded">{signal.suggested_action}</span>
                  </div>
                </div>
              ))}
           </div>
        </section>

        <section className="space-y-4">
           <div className="flex items-center gap-2 text-slate-500">
              <BadgeAlert className="w-5 h-5" />
              <h4 className="font-bold uppercase tracking-wider text-sm">阶段拦截 Intercepted</h4>
           </div>
           <div className="glass-panel p-8 text-center text-slate-500 italic text-sm">
              {data.stage_denied.length === 0 ? 'Today: No signals blocked by stage filters.' : `${data.stage_denied.length} signals blocked by stage filters.`}
           </div>
        </section>
      </div>
    </div>
  );
}

function LianbanPool({ candidates }: { candidates: LianbanCandidate[] }) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BadgeAlert className="w-6 h-6 text-accent-red" />
          <h3 className="text-xl font-bold tracking-tight">连板潜力 <span className="text-slate-500 font-normal ml-2">1-2 Board Watch</span></h3>
        </div>
        <span className="text-xs font-mono text-slate-500">{candidates.length} candidates</span>
      </div>

      <div className="glass-panel overflow-hidden rounded-xl">
        <div className="grid grid-cols-[1fr_0.55fr_0.7fr_0.8fr_0.65fr_1.4fr] gap-4 px-5 py-3 border-b border-border-subtle text-[10px] uppercase tracking-widest text-slate-500 font-mono">
          <span>Stock</span>
          <span>Height</span>
          <span>First Seal</span>
          <span>Strategy</span>
          <span>Score</span>
          <span>Action</span>
        </div>
        <div className="divide-y divide-border-subtle">
          {candidates.map((item) => (
            <div key={item.symbol} className="grid grid-cols-[1fr_0.55fr_0.7fr_0.8fr_0.65fr_1.4fr] gap-4 px-5 py-4 items-center hover:bg-white/[0.02] transition-colors">
              <div>
                <div className="font-bold text-slate-100">{item.name}</div>
                <div className="text-[10px] text-slate-500 font-mono">{item.symbol} · {item.sector || item.limit_type || '涨停'} · {stageLabel(item.stage)}</div>
              </div>
              <div className={cn("text-2xl font-black font-mono", item.lianban_count === 2 ? "text-accent-red" : "text-accent-orange")}>{item.lianban_count}板</div>
              <div className="text-xs font-mono text-slate-300">{item.first_time || '-'}</div>
              <Tag label={strategyLabel(item.strategy_name)} variant="outline" />
              <div className={cn("text-lg font-black font-mono", item.score >= 72 ? "text-accent-red" : item.score >= 58 ? "text-accent-orange" : "text-slate-400")}>{item.score.toFixed(0)}</div>
              <div>
                <div className="text-xs font-bold text-slate-200 mb-1">{actionLabel(item.action)} · {item.grade}</div>
                <div className="text-xs text-slate-400 line-clamp-2">{readableActionText(item.action_text)}</div>
              </div>
            </div>
          ))}
          {candidates.length === 0 && (
            <div className="p-8 text-center text-slate-500 italic text-sm">今日暂无一板/二板连板潜力候选，或涨停数据未同步完成。</div>
          )}
        </div>
      </div>
    </section>
  );
}

function StrategySignalPool({ signals }: { signals: StrategySignalCandidate[] }) {
  const visibleSignals = signals.filter((signal) => !signal.is_focus);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-accent-blue" />
          <h3 className="text-xl font-bold tracking-tight">策略信号池 <span className="text-slate-500 font-normal ml-2">Strategy Signals</span></h3>
        </div>
        <span className="text-xs font-mono text-slate-500">{visibleSignals.length} raw hits</span>
      </div>

      <div className="glass-panel overflow-hidden rounded-xl">
        <div className="grid grid-cols-[1.1fr_0.8fr_1fr_0.7fr_0.8fr_1.3fr] gap-4 px-5 py-3 border-b border-border-subtle text-[10px] uppercase tracking-widest text-slate-500 font-mono">
          <span>Symbol</span>
          <span>Sector</span>
          <span>Strategy</span>
          <span>Signal</span>
          <span>Price</span>
          <span>Action</span>
        </div>
        <div className="divide-y divide-border-subtle">
          {visibleSignals.map((signal) => (
            <div key={`${signal.strategy_name}-${signal.symbol}`} className="grid grid-cols-[1.1fr_0.8fr_1fr_0.7fr_0.8fr_1.3fr] gap-4 px-5 py-4 items-center hover:bg-white/[0.02] transition-colors">
              <div>
                <div className="font-bold text-slate-100">{signal.name}</div>
                <div className="text-[10px] text-slate-500 font-mono">{signal.symbol} · {signal.role} · {Math.round(signal.confidence * 100)}%</div>
              </div>
              <div>
                <div className="text-sm text-slate-200">{signal.sector || '-'}</div>
                <div className="text-[10px] text-slate-500 font-mono">{signal.sector_score.toFixed(1)} · {signal.sector_status}</div>
              </div>
              <Tag label={strategyLabel(signal.strategy_name)} variant="outline" />
              <div className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full", signal.action === 'buy' ? 'bg-accent-green' : 'bg-accent-blue')} />
                <span className="text-xs font-bold text-slate-200">{actionLabel(signal.action)}</span>
              </div>
              <div>
                <div className="font-mono text-sm">¥{formatPrice(signal.current_price)}</div>
                <div className={cn("text-[10px] font-bold", cnStockChange(signal.pct_chg))}>{formatPct(signal.pct_chg)}</div>
              </div>
              <div className="text-xs text-slate-300 line-clamp-2">{readableActionText(signal.action_text)}</div>
            </div>
          ))}
          {visibleSignals.length === 0 && (
            <div className="p-8 text-center text-slate-500 italic text-sm">暂无额外策略命中；当前所有可用信号都已进入重点池或被风控拦截。</div>
          )}
        </div>
      </div>
    </section>
  );
}

function MarketRiskCard({ risk }: { risk: any }) {
  const isRiskOn = risk.regime === 'risk_on';
  const color = isRiskOn ? 'text-accent-green' : risk.regime === 'weak' ? 'text-accent-red' : 'text-accent-blue';
  const bgColor = isRiskOn ? 'bg-accent-green/5' : risk.regime === 'weak' ? 'bg-accent-red/5' : 'bg-accent-blue/5';
  const borderColor = isRiskOn ? 'border-accent-green/20' : risk.regime === 'weak' ? 'border-accent-red/20' : 'border-accent-blue/20';

  return (
    <div className={cn("glass-panel p-6 rounded-xl flex flex-col justify-between relative overflow-hidden", bgColor, borderColor)}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-current opacity-[0.03] rounded-bl-full translate-x-8 -translate-y-8" />
      <div>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.2em]">Market Atmosphere</span>
          <Info className="w-4 h-4 text-slate-600" />
        </div>
        <div className="flex items-end gap-3 mb-2">
          <h2 className={cn("text-4xl font-black tracking-tighter uppercase", color)}>
            {risk.regime.replace('_', ' ')}
          </h2>
          <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold uppercase mb-1.5", isRiskOn ? 'bg-accent-green text-bg-dark' : 'bg-slate-700 text-white')}>
            {isRiskOn ? '进攻' : '防守'}
          </span>
        </div>
        <p className="text-xs text-slate-500 font-medium">指数处于 20 日线上方：{risk.index_above_ma20 ? 'YES' : 'NO'}</p>
      </div>

      <div className="mt-8">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="text-slate-400">涨跌比 Breadth</span>
          <span className="font-mono">{Math.round(risk.breadth * 100)}%</span>
        </div>
        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${risk.breadth * 100}%` }}
            className={cn("h-full", color.replace('text-', 'bg-'))}
          />
        </div>
      </div>
    </div>
  );
}

function MainlineSectorCard({ sector }: { sector: MainlineSector; key?: React.Key }) {
  const statusColors = {
    rising: 'text-accent-green',
    continuing: 'text-accent-blue',
    rotation: 'text-accent-orange',
    fading: 'text-accent-red'
  };

  return (
    <div className="glass-panel p-5 rounded-xl hover:bg-white/[0.02] transition-colors border-l-2 border-l-accent-blue">
       <div className="flex items-start justify-between">
          <div className="flex flex-col">
             <span className="font-bold text-lg">{sector.sector_name}</span>
             <span className="text-[10px] text-slate-500 uppercase tracking-widest font-mono">Top {sector.rank} Sector</span>
          </div>
          <div className="text-right">
             <div className="text-2xl font-black text-accent-blue font-mono">{sector.mainline_score}</div>
             <span className="text-[8px] text-slate-500 uppercase font-mono tracking-tighter">Score</span>
          </div>
       </div>

       <div className="mt-4 flex items-center justify-between">
          <div className="flex flex-col gap-1">
             <div className={cn("text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-white/5 w-fit", statusColors[sector.mainline_status])}>
                {sector.mainline_status}
             </div>
             <div className="text-[10px] text-slate-400">龙头：{sector.leader}</div>
          </div>
          <div className="flex gap-2">
             <div className="flex flex-col items-end">
                <span className="text-[10px] text-slate-500 font-mono">Limit Up</span>
                <span className="text-xs font-bold text-accent-orange">{sector.limit_up_count}</span>
             </div>
          </div>
       </div>
    </div>
  );
}

function StockFocusCard({ stock }: { stock: StockFocus; key?: React.Key }) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const gradeColor = stock.buy_grade === 'A' ? 'bg-accent-green' : 'bg-accent-orange';

  return (
    <div className={cn(
      "glass-panel rounded-xl overflow-hidden transition-all duration-300 border-l-[3px]",
      stock.buy_grade === 'A' ? "border-l-accent-green" : "border-l-accent-orange"
    )}>
       <div 
        className="p-5 flex items-center justify-between cursor-pointer group"
        onClick={() => setIsExpanded(!isExpanded)}
       >
          <div className="flex items-center gap-8 flex-1">
             <div className="flex flex-col">
                <div className="flex items-center gap-3">
                  <h4 className="text-xl font-bold">{stock.name}</h4>
                  <span className="text-xs text-slate-500 font-mono bg-white/5 px-2 py-0.5 rounded">{stock.symbol}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                   <div className={cn("px-2 py-0.5 rounded-[2px] text-[10px] font-black uppercase text-white shadow-lg", gradeColor)}>
                    {stock.buy_grade}档
                   </div>
                   <span className="text-xs text-slate-400">{stock.sector}</span>
                </div>
             </div>

             <div className="flex items-center gap-8">
                <div className="flex flex-col">
                   <span className="text-[10px] text-slate-500 uppercase font-mono font-medium">Price</span>
                   <div className="flex items-baseline gap-2">
                      <span className="text-lg font-bold font-mono">¥{formatPrice(stock.current_price)}</span>
                      <span className={cn("text-xs font-bold", cnStockChange(stock.pct_chg))}>
                        {formatPct(stock.pct_chg)}
                      </span>
                   </div>
                </div>

                <div className="hidden xl:flex items-center gap-3">
                   <Tag label={stageLabel(stock.stage)} color="bg-accent-blue/10 text-accent-blue border-accent-blue/20" />
                   <Tag label={strategyLabel(stock.strategy_name)} variant="outline" />
                </div>
             </div>

             <div className="flex-1 flex flex-col justify-center max-w-sm">
                <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono mb-1 px-1">
                   <span>Wait Range</span>
                   <span>Sell Guard</span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full relative flex items-center">
                   <div className="absolute h-full bg-accent-blue/40 rounded-full" style={{ left: '30%', right: '40%' }} />
                   <div className="absolute w-0.5 h-3 bg-accent-red translate-x-20" />
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono mt-1 px-1">
                   <span className="text-slate-300">¥{stock.entry_price_low} - ¥{stock.entry_price_high}</span>
                   <span className="text-accent-red">SL ¥{stock.stop_loss_price}</span>
                </div>
             </div>
          </div>

          <div className="flex items-center gap-8 pl-8">
             <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase font-mono text-slate-500">Action</span>
                <span className="text-sm font-bold text-slate-200">"{readableActionText(stock.action_text)}"</span>
             </div>
             <div className={cn("transform transition-transform duration-300", isExpanded && "rotate-180")}>
                <ChevronDown className="w-5 h-5 text-slate-500" />
             </div>
          </div>
       </div>

       {/* Expanded Details */}
       <motion.div
        initial={false}
        animate={{ height: isExpanded ? 'auto' : 0, opacity: isExpanded ? 1 : 0 }}
        className="overflow-hidden bg-bg-dark/50"
       >
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 border-t border-border-subtle">
             <DetailSection title="趋势与技术 Trend">
                <div className="space-y-2 text-sm">
                   <div className="flex justify-between"><span className="text-slate-500">State</span> <span className="text-slate-200 uppercase">{stock.trend.state}</span></div>
                   <div className="flex justify-between"><span className="text-slate-500">Alignment</span> <span className="text-slate-200">{stock.trend.ma_alignment}</span></div>
                   <div className="flex justify-between"><span className="text-slate-500">Slope (20)</span> <span className="text-accent-green font-mono">{stock.trend.slope_20}</span></div>
                </div>
             </DetailSection>

             <DetailSection title="量价分析 Vol/Price">
                <div className="space-y-2 text-sm">
                   <div className="flex justify-between"><span className="text-slate-500">Vol Ratio</span> <span className="text-slate-200 font-mono">{stock.volume_price.volume_ratio}x</span></div>
                   <div className="flex justify-between"><span className="text-slate-500">Status</span> <span className="text-accent-orange uppercase">{stock.volume_price.status}</span></div>
                   <div className="flex justify-between font-bold text-accent-green">
                      <TrendingUp className="w-4 h-4 mr-2" /> Healthy Accumulation
                   </div>
                </div>
             </DetailSection>

             <DetailSection title="风控与建议 Risk">
                <div className="space-y-2 text-sm">
                   <div className="flex justify-between"><span className="text-slate-500">Deny Check</span> <span className="text-accent-green font-bold">PASS ✓</span></div>
                   <div className="flex justify-between"><span className="text-slate-500">Pos Weight</span> <span className="text-slate-200 font-mono">{stock.position_pct * 100}%</span></div>
                   <div className="mt-2 text-[11px] text-slate-400 bg-white/5 p-2 rounded italic">
                      {stock.llm_review}
                   </div>
                </div>
             </DetailSection>

             <DetailSection title="板块深度 Sector">
                <div className="space-y-2 text-sm">
                   <div className="flex justify-between"><span className="text-slate-500">Strength</span> <span className="text-accent-blue font-bold tracking-widest">{stock.sector_detail.sector_score}</span></div>
                   <div className="flex justify-between"><span className="text-slate-500">Status</span> <span className="text-slate-200 capitalize">{stock.sector_detail.mainline_status}</span></div>
                </div>
                <div className="mt-4 flex items-center justify-end">
                   <span className="text-[10px] text-slate-600 font-mono">Data Quality: {stock.data_quality}</span>
                </div>
             </DetailSection>
          </div>
       </motion.div>
    </div>
  );
}

function DetailSection({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="space-y-3">
       <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-500 border-b border-border-subtle pb-1">{title}</h5>
       {children}
    </div>
  );
}

function Tag({ label, color, variant = 'filled' }: { label: string, color?: string, variant?: 'filled' | 'outline' }) {
  return (
    <span className={cn(
      "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
      variant === 'filled' ? color || "bg-white/10 text-slate-300" : cn("border bg-transparent", color || "border-slate-700 text-slate-500")
    )}>
      {label}
    </span>
  );
}
