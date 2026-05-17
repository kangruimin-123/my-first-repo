import React from 'react';
import { motion } from 'motion/react';
import { 
  Radar, 
  AlertOctagon, 
  Search, 
  Wind, 
  Activity,
  Flame,
  ArrowRight
} from 'lucide-react';
import { cn } from '../lib/utils';
import { MOCK_RADAR } from '../mock/data';
import { RadarSector, RiskWarning } from '../types';
import { api } from '../api/client';

export default function RadarView() {
  const [data, setData] = React.useState(MOCK_RADAR);

  React.useEffect(() => {
    api.radar().then(setData).catch(() => setData(MOCK_RADAR));
  }, []);

  const { mainline_radar, risk_warnings } = data;

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Radar className="w-8 h-8 text-accent-blue animate-pulse" />
          <div>
            <h3 className="text-2xl font-bold tracking-tight text-slate-100">核心雷达 Opportunity Radar</h3>
            <p className="text-sm text-slate-500">板块异动扫描与周期情绪监控</p>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        
        {/* Left: Plate Opportunities */}
        <div className="xl:col-span-2 space-y-6">
           <div className="flex items-center gap-2 mb-2">
              <Wind className="w-5 h-5 text-accent-blue" />
              <h4 className="font-bold uppercase tracking-wider text-sm opacity-80">明日关注板块 Focus Sectors</h4>
           </div>
           
           <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {mainline_radar.map((sector, i) => (
                <RadarSectorCard key={i} sector={sector} />
              ))}
              {mainline_radar.length === 0 && (
                <div className="glass-panel p-8 rounded-xl text-center text-slate-500 italic text-sm md:col-span-2">
                  暂无主线雷达预警。若需要扫描 Top6-20，打开后端 radar.mainline_radar.enabled。
                </div>
              )}
           </div>
        </div>

        {/* Right: Risk Warnings */}
        <div className="space-y-6">
          <div className="flex items-center gap-2 mb-2">
              <AlertOctagon className="w-5 h-5 text-accent-red" />
              <h4 className="font-bold uppercase tracking-wider text-sm opacity-80">退潮预警 Decay Warning</h4>
           </div>

           <div className="space-y-4">
              {risk_warnings.map((risk, i) => (
                <RiskWarningCard key={i} risk={risk} />
              ))}
              {risk_warnings.length === 0 && (
                <div className="glass-panel p-6 rounded-xl text-center text-slate-500 italic text-sm">
                  暂无退潮预警。
                </div>
              )}
           </div>
        </div>
      </div>
    </div>
  );
}

function RadarSectorCard({ sector }: { sector: RadarSector; key?: React.Key }) {
  return (
    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group hover:border-accent-blue/40 transition-all duration-300">
       <div className="absolute top-0 right-0 w-24 h-24 bg-accent-blue/10 blur-3xl -translate-y-8 translate-x-8 group-hover:scale-150 transition-transform duration-700" />
       
       <div className="flex items-start justify-between mb-6">
          <div>
             <h5 className="text-2xl font-black text-slate-100 group-hover:text-accent-blue transition-colors">{sector.sector_name}</h5>
             <span className="text-[10px] uppercase tracking-widest font-mono text-accent-blue font-bold">Signal: {sector.signal_type}</span>
          </div>
          <div className="p-3 bg-accent-blue/10 rounded-full border border-accent-blue/20">
             <div className="text-xl font-black font-mono text-accent-blue">{sector.radar_score}</div>
          </div>
       </div>

       <div className="space-y-3 mb-6">
          {sector.reason.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
               <Activity className="w-3 h-3 text-accent-blue opacity-50" />
               {r}
            </div>
          ))}
       </div>

       <div className="pt-4 border-t border-border-subtle">
          <div className="text-[9px] uppercase tracking-tighter text-slate-500 font-mono mb-3">Potential Leaders</div>
          <div className="space-y-2">
             {sector.suggested_watch.map((stock, i) => (
               <div key={i} className="flex items-center justify-between group/stock">
                  <div className="flex items-center gap-3">
                     <span className="text-sm font-bold text-slate-200">{stock.name}</span>
                     <span className="text-[10px] text-slate-500 font-mono">{stock.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2">
                     <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full bg-accent-blue" style={{ width: `${stock.probability * 100}%` }} />
                     </div>
                     <span className="text-[10px] font-mono text-accent-blue font-bold">{(stock.probability * 100).toFixed(0)}%</span>
                  </div>
               </div>
             ))}
          </div>
       </div>
    </div>
  );
}

function RiskWarningCard({ risk }: { risk: RiskWarning; key?: React.Key }) {
  const levelColors = {
    danger: 'border-accent-red text-accent-red bg-accent-red/5',
    caution: 'border-accent-orange text-accent-orange bg-accent-orange/5',
    watch: 'border-accent-blue text-accent-blue bg-accent-blue/5'
  };

  return (
    <div className={cn("p-5 rounded-xl border border-white/5 transition-all hover:bg-white/[0.03]", levelColors[risk.level])}>
       <div className="flex items-start justify-between mb-3">
          <div className="flex flex-col">
             <span className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
                <Flame className="w-4 h-4" />
                {risk.level}
             </span>
             <h6 className="text-lg font-bold text-slate-100 mt-1">{risk.target}</h6>
          </div>
          <span className="text-[10px] font-mono text-slate-500 px-2 py-1 bg-white/5 rounded uppercase">{risk.signal_type}</span>
       </div>
       
       <div className="space-y-1.5 mb-4">
          {risk.reason.map((r, i) => (
            <p key={i} className="text-xs text-slate-400 leading-relaxed">• {r}</p>
          ))}
       </div>

       <div className="flex items-center justify-between mt-auto">
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Recommended Action</span>
          <div className="flex items-center gap-2 font-bold px-3 py-1 bg-white/5 rounded-full border border-white/5 text-xs text-white">
             {risk.suggested_action}
             <ArrowRight className="w-3 h-3" />
          </div>
       </div>
    </div>
  );
}
