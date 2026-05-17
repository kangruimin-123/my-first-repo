import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  LayoutDashboard, 
  Radar, 
  Briefcase, 
  TrendingUp, 
  Settings, 
  Zap, 
  AlertTriangle, 
  CheckCircle2,
  Clock,
  ChevronRight,
  Menu,
  X,
  Target
} from 'lucide-react';
import { cn } from './lib/utils';

// Views
import OverviewView from './views/OverviewView';
import RadarView from './views/RadarView';
import PositionView from './views/PositionView';
import BacktestView from './views/BacktestView';
import SettingsView from './views/SettingsView';
import TodayDeskView from './views/TodayDeskView';

const NAV_ITEMS = [
  { id: 'today', name: '今日操作台', icon: Target },
  { id: 'overview', name: '每日总览', icon: LayoutDashboard },
  { id: 'radar', name: '机会雷达', icon: Radar },
  { id: 'positions', name: '持仓管理', icon: Briefcase },
  { id: 'backtest', name: '信号回测', icon: TrendingUp },
  { id: 'settings', name: '系统设置', icon: Settings },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('today');
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const renderView = () => {
    switch (activeTab) {
      case 'today': return <TodayDeskView />;
      case 'overview': return <OverviewView />;
      case 'radar': return <RadarView />;
      case 'positions': return <PositionView />;
      case 'backtest': return <BacktestView />;
      case 'settings': return <SettingsView />;
      default: return <OverviewView />;
    }
  };

  return (
    <div className="flex h-screen bg-bg-dark text-slate-100 overflow-hidden hud-grid">
      {/* Sidebar */}
      <motion.aside 
        initial={false}
        animate={{ width: isSidebarOpen ? 240 : 80 }}
        className="flex flex-col border-r border-border-subtle bg-bg-surface/80 backdrop-blur-md z-20"
      >
        <div className="p-6 flex items-center justify-between">
          <div className={cn("flex items-center gap-3 overflow-hidden transition-all", !isSidebarOpen && "scale-0 w-0")}>
            <div className="w-8 h-8 bg-accent-blue rounded flex items-center justify-center shadow-[0_0_15px_rgba(59,130,246,0.5)]">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold tracking-tight whitespace-nowrap">主线龙头系统</span>
          </div>
          <button 
            onClick={() => setSidebarOpen(!isSidebarOpen)}
            className="p-1 hover:bg-white/5 rounded transition-colors"
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  "w-full flex items-center gap-4 px-3 py-3 rounded-lg transition-all group relative overflow-hidden",
                  isActive 
                    ? "bg-accent-blue text-white shadow-[0_0_15px_rgba(59,130,246,0.3)]" 
                    : "text-slate-400 hover:text-slate-100 hover:bg-white/5"
                )}
              >
                <Icon className={cn("w-5 h-5 shrink-0", isActive ? "text-white" : "group-hover:text-accent-blue")} />
                {isSidebarOpen && <span className="font-medium whitespace-nowrap">{item.name}</span>}
                {isActive && (
                  <motion.div 
                    layoutId="active-pill"
                    className="absolute left-0 w-1 h-6 bg-white rounded-r-full"
                  />
                )}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border-subtle">
          <div className={cn("flex flex-col gap-1 transition-all overflow-hidden", !isSidebarOpen && "items-center")}>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              {isSidebarOpen && <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">System Live</span>}
            </div>
            {isSidebarOpen && (
              <div className="mt-2 p-3 bg-white/5 rounded border border-white/5">
                <div className="text-[10px] text-slate-500 uppercase mb-1 font-mono">Sync Status</div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span>Full Data</span>
                  <span className="text-accent-green">100%</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 relative h-full overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-bottom border-border-subtle bg-bg-surface/50 backdrop-blur-sm flex items-center justify-between px-8 z-10">
          <div className="flex items-center gap-6">
            <div className="flex flex-col">
              <h2 className="text-xl font-semibold tracking-tight">
                {NAV_ITEMS.find(i => i.id === activeTab)?.name}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">{currentTime.toLocaleDateString()}</span>
                <span className="text-[10px] text-accent-blue font-mono">{currentTime.toLocaleTimeString()}</span>
              </div>
            </div>
            <div className="h-8 w-px bg-border-subtle" />
            <div className="flex items-center gap-4">
              <StatusBadge label="Market Status" value="Normal" color="bg-accent-green" />
              <StatusBadge label="AI Signal" value="High Confidence" color="bg-accent-blue" />
            </div>
          </div>

          <div className="flex items-center gap-4">
             <div className="flex items-center gap-3 px-4 py-2 bg-white/5 rounded-full border border-white/10 group cursor-pointer hover:bg-white/10">
                <div className="w-2 h-2 bg-accent-orange rounded-full animate-ping" />
                <span className="text-xs font-medium">2 Urgent Warnings</span>
                <ChevronRight className="w-4 h-4 text-slate-500 group-hover:translate-x-1 transition-transform" />
             </div>
             <button className="p-2 bg-white/5 rounded-full border border-white/10 hover:bg-white/10 transition-colors">
                <Settings className="w-5 h-5 text-slate-400" />
             </button>
          </div>
        </header>

        {/* View Content */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-8 scrollbar-hide">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="max-w-[1600px] mx-auto w-full"
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ label, value, color }: { label: string, value: string, color: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] uppercase tracking-tighter text-slate-500 font-mono">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={cn("w-1.5 h-1.5 rounded-full", color)} />
        <span className="text-xs font-medium">{value}</span>
      </div>
    </div>
  )
}
