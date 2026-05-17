import React from 'react';
import { Database, RefreshCcw, Trash2, Clock, CheckCircle2, ShieldAlert } from 'lucide-react';
import { cn } from '../lib/utils';

export default function SettingsView() {
  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <section className="space-y-6">
        <h3 className="text-xl font-bold flex items-center gap-2">
          <Database className="w-5 h-5 text-accent-blue" />
          数据源状态 Data Sources
        </h3>
        
        <div className="space-y-4">
           <SourceItem name="Tushare Pro API" status="online" time="2026-05-16 15:30:02" latency="152ms" />
           <SourceItem name="AkShare Backend" status="online" time="2026-05-16 15:30:05" latency="420ms" />
           <SourceItem name="Local SQLite DB" status="online" time="2026-05-16 15:30:00" entries="1,425,000" />
           <SourceItem name="News Stream" status="degraded" time="2026-05-16 15:10:00" warning="Low coverage" />
        </div>
      </section>

      <section className="space-y-6 pt-8 border-t border-border-subtle">
        <h3 className="text-xl font-bold flex items-center gap-2">
          <RefreshCcw className="w-5 h-5 text-accent-orange" />
          系统维护 Maintenance
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
           <ActionTile 
              title="手动同步数据" 
              desc="重新从 API 拉取最新市场行情和主线评分" 
              icon={RefreshCcw} 
              btnText="Sync Now" 
            />
           <ActionTile 
              title="清理过期数据" 
              desc="删除 30 天前的计算缓存和日志文件" 
              icon={Trash2} 
              btnText="Purge Data" 
              danger 
            />
        </div>
      </section>

      <section className="space-y-4 pt-8 border-t border-border-subtle">
         <div className="p-6 bg-white/[0.02] border border-border-subtle rounded-2xl">
            <h4 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-4">Degradation Chain可视化</h4>
            <div className="flex items-center gap-4 text-xs font-mono">
               <div className="flex flex-col items-center gap-2">
                  <div className="px-4 py-2 border border-accent-green rounded bg-accent-green/10 text-accent-green">Tushare</div>
                  <CheckCircle2 className="w-4 h-4 text-accent-green" />
               </div>
               <div className="w-8 h-px bg-slate-700" />
               <div className="flex flex-col items-center gap-2">
                  <div className="px-4 py-2 border border-accent-blue rounded bg-accent-blue/10 text-accent-blue">AkShare</div>
                  <CheckCircle2 className="w-4 h-4 text-accent-green" />
               </div>
               <div className="w-8 h-px bg-slate-700" />
               <div className="flex flex-col items-center gap-2">
                  <div className="px-4 py-2 border border-slate-600 rounded bg-slate-100/5 text-slate-400 opacity-50">Local SQL</div>
                  <Clock className="w-4 h-4 text-slate-600" />
               </div>
            </div>
         </div>
      </section>
    </div>
  );
}

function SourceItem({ name, status, time, latency, entries, warning }: any) {
  const isOnline = status === 'online';
  const isDegraded = status === 'degraded';

  return (
    <div className="glass-panel p-4 rounded-xl flex items-center justify-between group">
       <div className="flex items-center gap-4">
          <div className={cn(
            "w-2 h-2 rounded-full",
            isOnline ? "bg-accent-green shadow-[0_0_8px_rgba(16,185,129,0.5)]" : 
            isDegraded ? "bg-accent-orange animate-pulse" : "bg-accent-red"
          )} />
          <div>
             <div className="font-bold text-slate-200">{name}</div>
             <div className="text-[10px] text-slate-500 font-mono uppercase tracking-tighter">
                Last Success: {time}
             </div>
          </div>
       </div>

       <div className="flex items-center gap-6">
          {latency && (
            <div className="text-right">
               <div className="text-[10px] text-slate-500 font-mono uppercase">Latency</div>
               <div className="text-xs font-mono text-slate-300">{latency}</div>
            </div>
          )}
          {entries && (
            <div className="text-right">
               <div className="text-[10px] text-slate-500 font-mono uppercase">Entries</div>
               <div className="text-xs font-mono text-slate-300">{entries}</div>
            </div>
          )}
          {warning && (
            <div className="px-2 py-1 bg-accent-orange/10 border border-accent-orange/20 rounded flex items-center gap-2 text-accent-orange">
               <ShieldAlert className="w-3 h-3" />
               <span className="text-[9px] font-bold uppercase">{warning}</span>
            </div>
          )}
          <button className="p-2 opacity-0 group-hover:opacity-100 transition-opacity">
             <RefreshCcw className="w-4 h-4 text-slate-500 hover:text-white" />
          </button>
       </div>
    </div>
  );
}

function ActionTile({ title, desc, icon: Icon, btnText, danger }: any) {
  return (
    <div className="glass-panel p-6 rounded-xl space-y-4">
       <div className="flex items-center gap-3">
          <div className={cn("p-2 rounded-lg", danger ? "bg-accent-red/10 text-accent-red" : "bg-accent-blue/10 text-accent-blue")}>
             <Icon className="w-5 h-5" />
          </div>
          <h5 className="font-bold text-slate-200">{title}</h5>
       </div>
       <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
       <button className={cn(
         "w-full py-2.5 rounded-lg text-xs font-bold transition-all",
         danger 
           ? "border border-accent-red/30 text-accent-red hover:bg-accent-red hover:text-white" 
           : "bg-accent-blue text-white hover:shadow-[0_0_15px_rgba(59,130,246,0.3)]"
       )}>
          {btnText}
       </button>
    </div>
  )
}
