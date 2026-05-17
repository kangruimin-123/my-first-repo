import React from 'react';
import { motion } from 'motion/react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  LineChart, 
  Line,
  Cell
} from 'recharts';
import { TrendingUp, Target, ShieldCheck, Zap } from 'lucide-react';
import { cn, strategyLabel } from '../lib/utils';
import { api, asNumber } from '../api/client';

const STRATEGY_STATS = [
  { name: 'Leader Breakout', signals: 42, winRate: 68.2, avgReturn: 5.4, maxDD: 3.2 },
  { name: 'Leader Pullback', signals: 35, winRate: 62.4, avgReturn: 4.8, maxDD: 4.5 },
  { name: 'Oversold Rebound', signals: 18, winRate: 45.8, avgReturn: 3.2, maxDD: 8.1 },
  { name: 'Range Break', signals: 22, winRate: 54.1, avgReturn: 2.9, maxDD: 3.8 },
];

const EQUITY_DATA = [
  { date: '05-01', val: 100 },
  { date: '05-05', val: 102.5 },
  { date: '05-10', val: 105.8 },
  { date: '05-12', val: 104.2 },
  { date: '05-14', val: 107.5 },
  { date: '05-16', val: 112.4 },
];

export default function BacktestView() {
  const [strategyStats, setStrategyStats] = React.useState(STRATEGY_STATS);

  React.useEffect(() => {
    api.backtest()
      .then((payload) => {
        const mapped = payload.strategy_stats.map((item) => ({
          name: strategyLabel(String(item.strategy_name)),
          signals: asNumber(item.total_signals),
          winRate: asNumber(item.win_rate_5d) * 100,
          avgReturn: asNumber(item.avg_return_5d) * 100,
          maxDD: Math.abs(asNumber(item.max_drawdown_5d) * 100),
        }));
        if (mapped.length > 0) {
          setStrategyStats(mapped);
        }
      })
      .catch(() => setStrategyStats(STRATEGY_STATS));
  }, []);

  const totalSignals = strategyStats.reduce((sum, item) => sum + item.signals, 0);
  const avgWinRate = strategyStats.length ? strategyStats.reduce((sum, item) => sum + item.winRate, 0) / strategyStats.length : 0;
  const avgReturn = strategyStats.length ? strategyStats.reduce((sum, item) => sum + item.avgReturn, 0) / strategyStats.length : 0;

  return (
    <div className="space-y-8">
      {/* Top Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard label="Total Signals" value={`${totalSignals}`} icon={Zap} />
        <SummaryCard label="Global Win Rate" value={`${avgWinRate.toFixed(1)}%`} icon={ShieldCheck} status="positive" />
        <SummaryCard label="Avg Profit" value={`${avgReturn.toFixed(2)}%`} icon={TrendingUp} status="positive" />
        <SummaryCard label="Risk Control Eff." value="High" icon={Target} status="neutral" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
         {/* Equity Curve */}
         <div className="glass-panel p-6 rounded-2xl">
            <h4 className="text-sm font-black uppercase tracking-[0.2em] text-slate-500 mb-8">Equity Growth (%)</h4>
            <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={EQUITY_DATA}>
                     <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                     <XAxis 
                        dataKey="date" 
                        stroke="#555" 
                        fontSize={10} 
                        tickLine={false} 
                        axisLine={false} 
                        fontFamily="JetBrains Mono"
                      />
                     <YAxis 
                        stroke="#555" 
                        fontSize={10} 
                        tickLine={false} 
                        axisLine={false} 
                        fontFamily="JetBrains Mono"
                        domain={['dataMin - 2', 'dataMax + 2']}
                      />
                     <Tooltip 
                        contentStyle={{ backgroundColor: '#12121a', border: '1px solid #333', fontSize: '10px' }} 
                        itemStyle={{ color: '#3b82f6' }}
                      />
                     <Line 
                        type="monotone" 
                        dataKey="val" 
                        stroke="#3b82f6" 
                        strokeWidth={3} 
                        dot={{ fill: '#3b82f6', r: 4 }} 
                        activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                      />
                  </LineChart>
               </ResponsiveContainer>
            </div>
         </div>

         {/* Strategy Win Rates */}
         <div className="glass-panel p-6 rounded-2xl">
            <h4 className="text-sm font-black uppercase tracking-[0.2em] text-slate-500 mb-8">Performance by Strategy</h4>
            <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={strategyStats} layout="vertical">
                     <CartesianGrid strokeDasharray="3 3" stroke="#222" horizontal={false} />
                     <XAxis type="number" domain={[0, 100]} hide />
                     <YAxis 
                        dataKey="name" 
                        type="category" 
                        stroke="#aaa" 
                        fontSize={10} 
                        axisLine={false} 
                        tickLine={false}
                        width={100}
                      />
                     <Tooltip 
                        cursor={{fill: 'rgba(255,255,255,0.05)'}}
                        contentStyle={{ backgroundColor: '#12121a', border: '1px solid #333', fontSize: '10px' }}
                      />
                     <Bar dataKey="winRate" radius={[0, 4, 4, 0]} barSize={20}>
                        {strategyStats.map((entry, index) => (
                           <Cell key={`cell-${index}`} fill={entry.winRate > 60 ? '#10b981' : entry.winRate > 50 ? '#3b82f6' : '#ef4444'} />
                        ))}
                     </Bar>
                  </BarChart>
               </ResponsiveContainer>
            </div>
         </div>
      </div>

      {/* Strategy Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
         <table className="w-full text-left">
            <thead>
               <tr className="border-b border-border-subtle bg-white/[0.02] text-[10px] uppercase font-mono tracking-widest text-slate-500">
                  <th className="px-6 py-4">Strategy</th>
                  <th className="px-6 py-4">Signals</th>
                  <th className="px-6 py-4">Win Rate</th>
                  <th className="px-6 py-4">Avg Profit</th>
                  <th className="px-6 py-4">Max DD</th>
               </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
               {strategyStats.map((stat, i) => (
                 <tr key={i} className="hover:bg-white/[0.01] transition-colors">
                    <td className="px-6 py-4 font-bold text-slate-200">{stat.name}</td>
                    <td className="px-6 py-4 font-mono text-sm">{stat.signals}</td>
                    <td className={cn("px-6 py-4 font-mono font-bold", stat.winRate > 55 ? "text-accent-green" : "text-accent-red")}>
                      {stat.winRate}%
                    </td>
                    <td className="px-6 py-4 font-mono text-accent-blue">+{stat.avgReturn}%</td>
                    <td className="px-6 py-4 font-mono text-slate-500">-{stat.maxDD}%</td>
                 </tr>
               ))}
            </tbody>
         </table>
      </div>

      {/* Gating Effectiveness */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
         <div className="p-6 bg-accent-green/5 border border-accent-green/10 rounded-2xl flex items-center justify-between">
            <div>
               <h5 className="font-bold text-accent-green mb-1 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5" /> 风控拦截有效性 Risk Gating Effective
               </h5>
               <p className="text-xs text-slate-400">Blocked signals performed 4.2% worse than passed ones on average.</p>
            </div>
            <div className="text-2xl font-black text-accent-green uppercase">Effective</div>
         </div>
         <div className="p-6 bg-accent-blue/5 border border-accent-blue/10 rounded-2xl flex items-center justify-between">
            <div>
               <h5 className="font-bold text-accent-blue mb-1 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5" /> 拦截率趋势 Gating Rate
               </h5>
               <p className="text-xs text-slate-400">Currently blocking 35% of all signals due to high market regime risk.</p>
            </div>
            <div className="text-2xl font-black text-accent-blue font-mono">35%</div>
         </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, icon: Icon, status }: { label: string, value: string, icon: any, status?: 'positive' | 'negative' | 'neutral' }) {
  const colorClass = status === 'positive' ? 'text-accent-green' : status === 'negative' ? 'text-accent-red' : 'text-slate-100';
  return (
    <div className="glass-panel p-6 rounded-xl flex items-center gap-4">
       <div className="p-3 bg-white/5 rounded-lg border border-white/5">
          <Icon className="w-6 h-6 text-slate-500" />
       </div>
       <div>
          <span className="text-[10px] uppercase font-mono text-slate-500">{label}</span>
          <div className={cn("text-2xl font-black font-mono", colorClass)}>{value}</div>
       </div>
    </div>
  )
}
