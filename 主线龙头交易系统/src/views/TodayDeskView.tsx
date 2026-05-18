import React from 'react';
import {
  BadgeAlert,
  Briefcase,
  CheckCircle2,
  Clock3,
  Eye,
  Radar,
  RefreshCcw,
  ShieldAlert,
  Target,
} from 'lucide-react';
import { api, TradeDayRunStatus } from '../api/client';
import { MOCK_EVALUATION, MOCK_POSITIONS, MOCK_RADAR } from '../mock/data';
import { EvaluationData, LianbanCandidate, Position, RadarData, StrategySignalCandidate, StockFocus } from '../types';
import { actionLabel, cn, cnStockChange, formatPct, formatPrice, readableActionText, stageLabel, strategyLabel } from '../lib/utils';

type DeskStatus = {
  latest_trade_date: string;
  trade_day?: {
    last_phase: string;
    last_message: string;
    last_detail: string;
    last_run_at: string;
  };
};

type DeskCandidate = {
  symbol: string;
  name: string;
  sector: string;
  strategy: string;
  action: string;
  actionText: string;
  grade: string;
  score: number;
  confidence: number;
  currentPrice: number;
  pctChg: number;
  entryLow?: number;
  entryHigh?: number;
  stopLoss?: number;
  source: 'focus' | 'signal' | 'lianban';
};

export default function TodayDeskView() {
  const [evaluation, setEvaluation] = React.useState<EvaluationData>(MOCK_EVALUATION);
  const [radar, setRadar] = React.useState<RadarData>(MOCK_RADAR);
  const [positions, setPositions] = React.useState<Position[]>(MOCK_POSITIONS);
  const [status, setStatus] = React.useState<DeskStatus | null>(null);
  const [isLive, setIsLive] = React.useState(false);
  const [runningPhase, setRunningPhase] = React.useState('');
  const [phaseResult, setPhaseResult] = React.useState<TradeDayRunStatus | null>(null);
  const [phaseError, setPhaseError] = React.useState('');

  const loadDeskData = React.useCallback(() => {
    Promise.allSettled([api.evaluation(), api.radar(), api.positions(), api.status()]).then((results) => {
      const [evaluationResult, radarResult, positionsResult, statusResult] = results;
      if (evaluationResult.status === 'fulfilled') {
        setEvaluation(evaluationResult.value);
        setIsLive(true);
      }
      if (radarResult.status === 'fulfilled') setRadar(radarResult.value);
      if (positionsResult.status === 'fulfilled') setPositions(positionsResult.value);
      if (statusResult.status === 'fulfilled') setStatus(statusResult.value);
    });
  }, []);

  React.useEffect(() => {
    loadDeskData();
  }, [loadDeskData]);

  const runTradePhase = React.useCallback(async (phase: 'opening' | 'intraday' | 'review') => {
    setRunningPhase(phase);
    setPhaseError('');
    try {
      const result = await api.runTradeDayPhase(phase);
      setPhaseResult(result);
      loadDeskData();
    } catch (error) {
      setPhaseError(error instanceof Error ? error.message : '任务启动失败');
    } finally {
      setRunningPhase('');
    }
  }, [loadDeskData]);

  const rawBuyList = buildBuyList(evaluation);
  const rawObserveList = buildObserveList(evaluation);
  const rawBlockedList = buildBlockedList(evaluation);
  const buySymbols = new Set(rawBuyList.map((item) => item.symbol));
  const observeSymbols = new Set(rawObserveList.filter((item) => !buySymbols.has(item.symbol)).map((item) => item.symbol));
  const buyList = rawBuyList.slice(0, 8);
  const observeList = rawObserveList.filter((item) => !buySymbols.has(item.symbol)).slice(0, 8);
  const blockedList = rawBlockedList.filter((item) => !buySymbols.has(item.symbol) && !observeSymbols.has(item.symbol)).slice(0, 6);
  const positionActions = [
    ...positions.filter((item) => item.action_suggestion !== 'hold').map(positionToAction),
    ...(evaluation.sell_signals || []).map((item) => ({
      symbol: item.symbol,
      name: item.name,
      action: item.suggested_action || '卖出预警',
      reason: item.reason,
      level: 'danger' as const,
    })),
  ].slice(0, 6);

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 xl:grid-cols-[1.25fr_0.75fr] gap-6">
        <div className="glass-panel rounded-xl p-6 overflow-hidden relative">
          <div className="absolute right-0 top-0 w-48 h-48 bg-accent-blue/10 blur-3xl translate-x-16 -translate-y-16" />
          <div className="relative flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Target className="w-7 h-7 text-accent-orange" />
                <h3 className="text-2xl font-black tracking-tight text-slate-100">今日操作台</h3>
                <span className="px-2 py-1 rounded bg-accent-blue/10 border border-accent-blue/20 text-[10px] font-mono text-accent-blue">
                  {isLive ? 'Live API' : 'Mock Fallback'}
                </span>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
                先处理持仓风险，再看可买清单；可买必须同时满足策略、阶段、止损和市场环境，观察池只盯触发确认。
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 min-w-[300px]">
              <MiniStat label="可买" value={buyList.length} tone="red" />
              <MiniStat label="观察" value={observeList.length} tone="blue" />
              <MiniStat label="风险" value={positionActions.length} tone={positionActions.length ? 'orange' : 'green'} />
              <MiniStat label="雷达" value={radar.mainline_radar.length} tone="green" />
            </div>
          </div>
        </div>

        <div className="glass-panel rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock3 className="w-5 h-5 text-accent-blue" />
            <h4 className="font-bold text-slate-100">交易日状态</h4>
          </div>
          <div className="grid grid-cols-3 gap-2 mb-4">
            <PhaseButton label="盘前" subLabel="竞价" phase="opening" runningPhase={runningPhase} onRun={runTradePhase} />
            <PhaseButton label="盘中" subLabel="监控" phase="intraday" runningPhase={runningPhase} onRun={runTradePhase} />
            <PhaseButton label="盘后" subLabel="复盘" phase="review" runningPhase={runningPhase} onRun={runTradePhase} />
          </div>
          <div className="space-y-3 text-sm">
            <StatusLine label="交易日" value={status?.latest_trade_date || evaluation.date || '-'} />
            <StatusLine label="最近任务" value={phaseLabel(status?.trade_day?.last_phase || '')} />
            <StatusLine label="更新时间" value={formatTime(status?.trade_day?.last_run_at || '')} />
          </div>
          <div className="mt-4 rounded-lg bg-white/[0.03] border border-border-subtle px-4 py-3 text-xs text-slate-400 leading-relaxed">
            {status?.trade_day?.last_message || '暂无调度状态'}
          </div>
          {(phaseResult?.detail || status?.trade_day?.last_detail) && (
            <div className="mt-3 rounded-lg bg-accent-blue/5 border border-accent-blue/10 px-4 py-3 text-[11px] text-slate-400 leading-relaxed">
              {phaseResult?.detail || status?.trade_day?.last_detail}
            </div>
          )}
          {phaseError && <div className="mt-3 text-xs text-accent-red">{phaseError}</div>}
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <DeskPanel icon={CheckCircle2} title="今日可买" subTitle="Buy List" count={buyList.length} tone="red">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {buyList.map((item) => <CandidateCard key={`${item.source}-${item.symbol}-${item.strategy}`} item={item} primary />)}
              {buyList.length === 0 && <EmptyState text="今天没有满足买入条件的标的，优先看观察池等待确认。" />}
            </div>
          </DeskPanel>

          <DeskPanel icon={Eye} title="只观察" subTitle="Watch Only" count={observeList.length} tone="blue">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {observeList.map((item) => <CandidateCard key={`${item.source}-${item.symbol}-${item.strategy}`} item={item} />)}
              {observeList.length === 0 && <EmptyState text="暂无观察候选。" />}
            </div>
          </DeskPanel>
        </div>

        <div className="space-y-6">
          <DeskPanel icon={Briefcase} title="持仓处理" subTitle="Position Actions" count={positionActions.length} tone="orange">
            <div className="space-y-3">
              {positionActions.map((item) => <ActionCard key={`${item.symbol}-${item.action}`} item={item} />)}
              {positionActions.length === 0 && <EmptyState text="当前持仓暂无卖出/减仓预警。" compact />}
            </div>
          </DeskPanel>

          <DeskPanel icon={ShieldAlert} title="禁止追" subTitle="Blocked" count={blockedList.length} tone="slate">
            <div className="space-y-3">
              {blockedList.map((item) => <BlockedCard key={`${item.symbol}-${item.strategy}`} item={item} />)}
              {blockedList.length === 0 && <EmptyState text="暂无阶段或风控拦截。" compact />}
            </div>
          </DeskPanel>

          <DeskPanel icon={Radar} title="方向雷达" subTitle="Sectors" count={radar.mainline_radar.length} tone="green">
            <div className="space-y-3">
              {radar.mainline_radar.slice(0, 5).map((sector) => (
                <div key={sector.sector_name} className="rounded-lg border border-border-subtle bg-white/[0.02] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-bold text-slate-100">{sector.sector_name}</div>
                    <div className="text-sm font-black text-accent-green font-mono">{sector.radar_score}</div>
                  </div>
                  <div className="mt-2 text-xs text-slate-400 line-clamp-2">{sector.reason.join('；')}</div>
                </div>
              ))}
              {radar.mainline_radar.length === 0 && <EmptyState text="暂无机会雷达板块。" compact />}
            </div>
          </DeskPanel>
        </div>
      </section>
    </div>
  );
}

function buildBuyList(data: EvaluationData): DeskCandidate[] {
  const focus = (data.focus_pool || [])
    .filter((item) => ['buy', 'add'].includes(item.action) && ['A', 'B'].includes(item.buy_grade))
    .map(focusToCandidate);
  const signals = (data.strategy_signal_pool || [])
    .filter((item) => ['buy', 'add'].includes(item.action) && ['A', 'B'].includes(item.grade))
    .map(signalToCandidate);
  const lianban = (data.lianban_pool || [])
    .filter((item) => item.score >= 72 || (item.lianban_count === 2 && item.confidence >= 0.6))
    .map(lianbanToCandidate);
  return dedupeCandidates([...focus, ...lianban, ...signals]).sort((a, b) => b.score - a.score);
}

function buildObserveList(data: EvaluationData): DeskCandidate[] {
  const focus = (data.focus_pool || [])
    .filter((item) => ['watch', 'hold'].includes(item.action) && item.buy_grade !== 'SELL')
    .map(focusToCandidate);
  const signals = (data.strategy_signal_pool || [])
    .filter((item) => ['watch', 'hold'].includes(item.action) && item.grade !== 'SELL')
    .map(signalToCandidate);
  const lianban = (data.lianban_pool || []).map(lianbanToCandidate);
  return dedupeCandidates([...lianban, ...focus, ...signals]).sort((a, b) => b.score - a.score);
}

function buildBlockedList(data: EvaluationData): DeskCandidate[] {
  const signals = (data.strategy_signal_pool || [])
    .filter((item) => item.action === 'deny')
    .map(signalToCandidate);
  const denied = (data.stage_denied || []).map((item: any) => ({
    symbol: item.symbol || '',
    name: item.name || item.symbol || '阶段拦截',
    sector: item.sector || '',
    strategy: item.strategy_name || '',
    action: 'deny',
    actionText: item.reason || item.action_text || '阶段门控或风控条件不允许买入',
    grade: item.grade || 'NONE',
    score: 0,
    confidence: 0,
    currentPrice: 0,
    pctChg: 0,
    source: 'signal' as const,
  }));
  return dedupeCandidates([...signals, ...denied]);
}

function focusToCandidate(item: StockFocus): DeskCandidate {
  return {
    symbol: item.symbol,
    name: item.name,
    sector: item.sector,
    strategy: item.strategy_name,
    action: item.action,
    actionText: item.action_text,
    grade: item.buy_grade,
    score: item.buy_score,
    confidence: item.confidence,
    currentPrice: item.current_price,
    pctChg: item.pct_chg,
    entryLow: item.entry_price_low,
    entryHigh: item.entry_price_high,
    stopLoss: item.stop_loss_price,
    source: 'focus',
  };
}

function signalToCandidate(item: StrategySignalCandidate): DeskCandidate {
  return {
    symbol: item.symbol,
    name: item.name,
    sector: item.sector,
    strategy: item.strategy_name,
    action: item.action,
    actionText: item.action_text,
    grade: item.grade,
    score: Math.round(item.confidence * 100),
    confidence: item.confidence,
    currentPrice: item.current_price,
    pctChg: item.pct_chg,
    entryLow: item.entry_price_low,
    entryHigh: item.entry_price_high,
    stopLoss: item.stop_loss_price,
    source: 'signal',
  };
}

function lianbanToCandidate(item: LianbanCandidate): DeskCandidate {
  return {
    symbol: item.symbol,
    name: item.name,
    sector: item.sector,
    strategy: item.strategy_name,
    action: item.action,
    actionText: item.action_text,
    grade: item.grade,
    score: item.score,
    confidence: item.confidence,
    currentPrice: 0,
    pctChg: 0,
    source: 'lianban',
  };
}

function positionToAction(item: Position) {
  return {
    symbol: item.symbol,
    name: item.name,
    action: actionLabel(item.action_suggestion),
    reason: `${stageLabel(item.stage)}；${item.trend_state}；止损 ${formatPrice(item.stop_loss)}`,
    level: item.action_suggestion === 'sell' ? 'danger' as const : 'caution' as const,
  };
}

function dedupeCandidates(items: DeskCandidate[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.symbol}-${item.strategy}-${item.source}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function DeskPanel({
  icon: Icon,
  title,
  subTitle,
  count,
  tone,
  children,
}: {
  icon: React.ElementType;
  title: string;
  subTitle: string;
  count: number;
  tone: 'red' | 'blue' | 'green' | 'orange' | 'slate';
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Icon className={cn('w-6 h-6', toneText(tone))} />
          <h3 className="text-xl font-bold tracking-tight">
            {title} <span className="text-slate-500 font-normal ml-2">{subTitle}</span>
          </h3>
        </div>
        <span className="text-xs font-mono text-slate-500">{count} items</span>
      </div>
      {children}
    </section>
  );
}

function CandidateCard({ item, primary = false }: { item: DeskCandidate; primary?: boolean; key?: React.Key }) {
  return (
    <article className={cn('glass-panel rounded-xl p-5 border transition-colors', primary ? 'border-accent-red/25 bg-accent-red/[0.03]' : 'border-border-subtle')}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-lg font-black text-slate-100">{item.name}</h4>
            <span className="text-[10px] text-slate-500 font-mono">{item.symbol}</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">{item.sector || '未归属板块'} · {strategyLabel(item.strategy)}</div>
        </div>
        <div className={cn('px-2 py-1 rounded text-[10px] font-black', gradeClass(item.grade))}>{item.grade}</div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <Metric label="动作" value={actionLabel(item.action)} tone={primary ? 'red' : 'blue'} />
        <Metric label="分数" value={item.score.toFixed(0)} tone="slate" />
        <Metric label="信心" value={`${Math.round(item.confidence * 100)}%`} tone="slate" />
      </div>

      {(item.currentPrice > 0 || item.entryLow || item.stopLoss) && (
        <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
          <PriceBox label="现价" value={item.currentPrice > 0 ? `¥${formatPrice(item.currentPrice)}` : '-'} sub={item.currentPrice > 0 ? formatPct(item.pctChg) : ''} pct={item.pctChg} />
          <PriceBox label="买点" value={item.entryLow ? `${formatPrice(item.entryLow)}-${formatPrice(item.entryHigh || item.entryLow)}` : '-'} />
          <PriceBox label="止损" value={item.stopLoss ? formatPrice(item.stopLoss) : '-'} />
        </div>
      )}

      <p className="mt-4 text-xs leading-relaxed text-slate-400 line-clamp-3">{readableActionText(item.actionText)}</p>
    </article>
  );
}

function ActionCard({ item }: { item: { symbol: string; name: string; action: string; reason: string; level: 'danger' | 'caution' }; key?: React.Key }) {
  return (
    <div className={cn('rounded-lg border p-4', item.level === 'danger' ? 'border-accent-red/25 bg-accent-red/[0.04]' : 'border-accent-orange/25 bg-accent-orange/[0.04]')}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-bold text-slate-100">{item.name}</div>
          <div className="text-[10px] text-slate-500 font-mono">{item.symbol}</div>
        </div>
        <span className={cn('px-2 py-1 rounded text-[10px] font-black text-white', item.level === 'danger' ? 'bg-accent-red' : 'bg-accent-orange')}>{item.action}</span>
      </div>
      <div className="mt-3 text-xs leading-relaxed text-slate-400">{item.reason}</div>
    </div>
  );
}

function BlockedCard({ item }: { item: DeskCandidate; key?: React.Key }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-white/[0.02] p-4">
      <div className="flex items-center gap-2">
        <BadgeAlert className="w-4 h-4 text-slate-500" />
        <div className="font-bold text-slate-200">{item.name}</div>
        <div className="text-[10px] text-slate-500 font-mono">{item.symbol}</div>
      </div>
      <div className="mt-2 text-xs text-slate-500">{strategyLabel(item.strategy)}</div>
      <div className="mt-2 text-xs text-slate-400 line-clamp-2">{readableActionText(item.actionText)}</div>
    </div>
  );
}

function PhaseButton({
  label,
  subLabel,
  phase,
  runningPhase,
  onRun,
}: {
  label: string;
  subLabel: string;
  phase: 'opening' | 'intraday' | 'review';
  runningPhase: string;
  onRun: (phase: 'opening' | 'intraday' | 'review') => void;
}) {
  const isRunning = runningPhase === phase;
  return (
    <button
      className={cn(
        'rounded-lg border border-border-subtle bg-white/[0.03] px-3 py-2 text-left transition-all hover:border-accent-blue/40 hover:bg-accent-blue/10',
        runningPhase && !isRunning && 'opacity-50',
      )}
      disabled={Boolean(runningPhase)}
      onClick={() => onRun(phase)}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-black text-slate-100">{label}</span>
        <RefreshCcw className={cn('w-3.5 h-3.5 text-accent-blue', isRunning && 'animate-spin')} />
      </div>
      <div className="mt-0.5 text-[10px] text-slate-500">{isRunning ? '运行中' : subLabel}</div>
    </button>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone: 'red' | 'blue' | 'green' | 'orange' }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-white/[0.03] px-4 py-3">
      <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">{label}</div>
      <div className={cn('mt-1 text-2xl font-black font-mono', toneText(tone))}>{value}</div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: 'red' | 'blue' | 'slate' }) {
  return (
    <div className="rounded-lg bg-white/[0.03] border border-border-subtle px-3 py-2">
      <div className="text-[9px] text-slate-500 font-mono uppercase">{label}</div>
      <div className={cn('mt-1 text-sm font-black', toneText(tone))}>{value}</div>
    </div>
  );
}

function PriceBox({ label, value, sub = '', pct = 0 }: { label: string; value: string; sub?: string; pct?: number }) {
  return (
    <div className="rounded-lg bg-black/10 border border-border-subtle px-3 py-2 min-w-0">
      <div className="text-[9px] text-slate-500 font-mono uppercase">{label}</div>
      <div className="mt-1 text-xs font-bold text-slate-200 truncate">{value}</div>
      {sub && <div className={cn('mt-0.5 text-[10px] font-bold', cnStockChange(pct))}>{sub}</div>}
    </div>
  );
}

function EmptyState({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div className={cn('glass-panel rounded-xl text-center text-slate-500 italic text-sm', compact ? 'p-5' : 'p-8')}>
      {text}
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-xs text-slate-200 text-right">{value || '-'}</span>
    </div>
  );
}

function phaseLabel(value: string) {
  const labels: Record<string, string> = {
    opening: '开盘指导',
    intraday: '盘中监控',
    review: '盘后复盘',
    idle: '等待时段',
  };
  return labels[value] || '未运行';
}

function formatTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function gradeClass(value: string) {
  if (value === 'A') return 'bg-accent-red text-white';
  if (value === 'B') return 'bg-accent-orange text-white';
  if (value === 'SELL') return 'bg-accent-green text-white';
  return 'bg-white/5 text-slate-400';
}

function toneText(tone: 'red' | 'blue' | 'green' | 'orange' | 'slate') {
  const tones = {
    red: 'text-accent-red',
    blue: 'text-accent-blue',
    green: 'text-accent-green',
    orange: 'text-accent-orange',
    slate: 'text-slate-300',
  };
  return tones[tone];
}
