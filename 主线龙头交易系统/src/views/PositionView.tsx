import React from 'react';
import {
  AlertTriangle,
  Briefcase,
  Eye,
  Layers,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  WalletCards,
} from 'lucide-react';
import { api } from '../api/client';
import { cn, cnStockChange, formatPct, formatPrice, readableActionText, stageLabel, strategyLabel } from '../lib/utils';
import { MOCK_POSITIONS } from '../mock/data';
import { NewPositionInput, Position, WatchlistItem } from '../types';

type PoolTab = 'watchlist' | 'positions';

const emptyForm: NewPositionInput = {
  symbol: '',
  name: '',
  entry_price: 0,
  entry_date: new Date().toISOString().slice(0, 10),
  quantity: 100,
  stop_loss: 0,
  notes: '',
};

export default function PositionView() {
  const [activePool, setActivePool] = React.useState<PoolTab>('watchlist');
  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([]);
  const [positions, setPositions] = React.useState<Position[]>([]);
  const [query, setQuery] = React.useState('');
  const [showForm, setShowForm] = React.useState(false);
  const [form, setForm] = React.useState<NewPositionInput>(emptyForm);
  const [isSaving, setIsSaving] = React.useState(false);

  const loadPools = React.useCallback(() => {
    api.watchlist().then(setWatchlist).catch(() => setWatchlist([]));
    api.positions().then(setPositions).catch(() => setPositions(MOCK_POSITIONS));
  }, []);

  React.useEffect(() => {
    loadPools();
  }, [loadPools]);

  const filteredWatchlist = watchlist.filter((item) => {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [item.symbol, item.name, item.group, item.strategy_name].some((value) => value.toLowerCase().includes(needle));
  });

  const totalValue = positions.reduce((sum, item) => sum + item.market_value, 0);
  const totalPnl = positions.reduce((sum, item) => sum + item.pnl_amount, 0);
  const riskCount = positions.filter((item) => item.action_suggestion !== 'hold').length;

  const submitPosition = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      await api.createPosition({
        ...form,
        symbol: form.symbol.trim(),
        name: form.name?.trim(),
        entry_price: Number(form.entry_price),
        quantity: Number(form.quantity),
        stop_loss: Number(form.stop_loss || 0),
      });
      setForm(emptyForm);
      setShowForm(false);
      setActivePool('positions');
      loadPools();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Watchlist" value={`${watchlist.length}`} subValue="候选观察" color="text-accent-blue" />
        <StatCard label="Positions" value={`${positions.length}`} subValue="手工持仓" color="text-accent-orange" />
        <StatCard label="Market Value" value={`¥${formatPrice(totalValue)}`} subValue={`PNL ¥${formatPrice(totalPnl)}`} color={cnStockChange(totalPnl)} />
        <StatCard label="Risk Alerts" value={`${riskCount}`} subValue="止损/减仓触发" color={riskCount ? 'text-accent-red' : 'text-accent-green'} />
      </div>

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="inline-flex w-fit rounded-lg border border-border-subtle bg-bg-surface p-1">
          <PoolButton icon={Eye} label="自选池" active={activePool === 'watchlist'} onClick={() => setActivePool('watchlist')} />
          <PoolButton icon={Briefcase} label="持仓池" active={activePool === 'positions'} onClick={() => setActivePool('positions')} />
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          {activePool === 'watchlist' && (
            <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border-subtle bg-bg-surface text-sm text-slate-400">
              <Search className="w-4 h-4" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索代码、名称、板块"
                className="bg-transparent outline-none text-slate-100 placeholder:text-slate-600"
              />
            </label>
          )}
          <button
            onClick={loadPools}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-border-subtle bg-bg-surface text-xs font-bold text-slate-300 hover:bg-white/5"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={() => {
              setShowForm((value) => !value);
              setActivePool('positions');
            }}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-accent-blue text-white text-xs font-bold hover:shadow-[0_0_15px_rgba(59,130,246,0.4)]"
          >
            <Plus className="w-4 h-4" /> Add Position
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={submitPosition} className="glass-panel rounded-xl p-5 grid grid-cols-1 md:grid-cols-6 gap-4">
          <Field label="代码" value={form.symbol} onChange={(value) => setForm({ ...form, symbol: value })} placeholder="301291.SZ" required />
          <Field label="名称" value={form.name || ''} onChange={(value) => setForm({ ...form, name: value })} placeholder="可选" />
          <Field label="买入价" type="number" value={form.entry_price || ''} onChange={(value) => setForm({ ...form, entry_price: Number(value) })} required />
          <Field label="数量" type="number" value={form.quantity || ''} onChange={(value) => setForm({ ...form, quantity: Number(value) })} required />
          <Field label="买入日" type="date" value={form.entry_date} onChange={(value) => setForm({ ...form, entry_date: value })} required />
          <Field label="止损价" type="number" value={form.stop_loss || ''} onChange={(value) => setForm({ ...form, stop_loss: Number(value) })} />
          <label className="md:col-span-5 flex flex-col gap-2">
            <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Notes</span>
            <input
              value={form.notes || ''}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
              className="px-3 py-2 rounded-lg bg-white/5 border border-border-subtle outline-none text-sm text-slate-100"
              placeholder="买入逻辑、计划、止盈条件"
            />
          </label>
          <button disabled={isSaving} className="self-end px-4 py-2 rounded-lg bg-accent-green text-white text-xs font-black disabled:opacity-50">
            {isSaving ? 'Saving' : 'Save'}
          </button>
        </form>
      )}

      {activePool === 'watchlist' ? <WatchlistPanel items={filteredWatchlist} /> : <PositionPanel positions={positions} />}
    </div>
  );
}

function PoolButton({ icon: Icon, label, active, onClick }: { icon: React.ElementType; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-bold transition-colors',
        active ? 'bg-accent-blue text-white' : 'text-slate-400 hover:text-slate-100'
      )}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
}

function WatchlistPanel({ items }: { items: WatchlistItem[] }) {
  return (
    <section className="glass-panel rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border-subtle flex items-center justify-between">
        <h3 className="font-bold flex items-center gap-2">
          <Layers className="w-5 h-5 text-accent-blue" />
          自选池 Watchlist
        </h3>
        <span className="text-xs font-mono text-slate-500">{items.length} stocks</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-px bg-border-subtle">
        {items.map((item) => (
          <WatchlistCard key={item.symbol} item={item} />
        ))}
        {items.length === 0 && <div className="bg-bg-surface px-6 py-10 text-center text-sm text-slate-500">暂无自选股。</div>}
      </div>
    </section>
  );
}

function WatchlistCard({ item }: { item: WatchlistItem; key?: React.Key }) {
  const blocked = item.action === 'deny';
  return (
    <article className="bg-bg-surface p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-bold text-slate-100">{item.name}</div>
          <div className="text-[11px] font-mono text-slate-500 mt-1">{item.symbol}</div>
        </div>
        <span className={cn('text-[10px] px-2 py-1 rounded font-black', gradeClass(item.buy_grade))}>{item.buy_grade}</span>
      </div>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Price</div>
          <div className="text-xl font-black font-mono">¥{formatPrice(item.current_price)}</div>
        </div>
        <div className={cn('text-lg font-black font-mono', cnStockChange(item.pct_chg))}>{formatPct(item.pct_chg)}</div>
      </div>
      <div className="flex flex-wrap gap-2 text-[10px]">
        <span className="px-2 py-1 rounded bg-white/5 text-slate-300">{item.group}</span>
        {item.stage && <span className="px-2 py-1 rounded bg-white/5 text-slate-300">{stageLabel(item.stage)}</span>}
        {item.strategy_name && <span className="px-2 py-1 rounded bg-accent-blue/10 text-accent-blue">{strategyLabel(item.strategy_name)}</span>}
      </div>
      <div className={cn('text-xs leading-relaxed', blocked ? 'text-accent-red' : 'text-slate-400')}>
        {readableActionText(item.action_text)}
      </div>
    </article>
  );
}

function PositionPanel({ positions }: { positions: Position[] }) {
  return (
    <section className="glass-panel rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border-subtle flex items-center justify-between">
        <h3 className="font-bold flex items-center gap-2">
          <WalletCards className="w-5 h-5 text-accent-orange" />
          持仓池 Position Pool
        </h3>
        <span className="text-xs font-mono text-slate-500">{positions.length} positions</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[840px] text-left">
          <thead>
            <tr className="border-b border-border-subtle bg-white/[0.02] text-[10px] uppercase font-mono tracking-widest text-slate-500">
              <th className="px-6 py-4">Stock</th>
              <th className="px-6 py-4">Position</th>
              <th className="px-6 py-4">Risk</th>
              <th className="px-6 py-4 text-right">Price</th>
              <th className="px-6 py-4 text-right">PNL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {positions.map((position) => (
              <PositionRow key={`${position.symbol}-${position.entry_date}`} position={position} />
            ))}
            {positions.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-slate-500 italic text-sm">
                  暂无手工持仓。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PositionRow({ position }: { position: Position; key?: React.Key }) {
  const actionClass = position.action_suggestion === 'hold'
    ? 'bg-accent-green text-white'
    : position.action_suggestion === 'reduce'
      ? 'bg-accent-orange text-white'
      : 'bg-accent-red text-white';
  const actionText = position.action_suggestion === 'hold' ? '持有' : position.action_suggestion === 'reduce' ? '减仓' : '卖出';
  return (
    <tr className="hover:bg-white/[0.01] transition-colors">
      <td className="px-6 py-5">
        <div className="font-bold text-slate-100">{position.name}</div>
        <div className="text-[10px] font-mono text-slate-500 mt-1">{position.symbol}</div>
      </td>
      <td className="px-6 py-5">
        <div className="text-sm text-slate-300">{position.quantity.toLocaleString()} 股</div>
        <div className="text-[10px] font-mono text-slate-500 mt-1">{position.hold_days}d Held</div>
      </td>
      <td className="px-6 py-5">
        <div className="flex items-center gap-2 text-[11px] text-slate-300">
          {position.action_suggestion === 'hold' ? <ShieldCheck className="w-4 h-4 text-accent-green" /> : <AlertTriangle className="w-4 h-4 text-accent-red" />}
          <span className={cn('text-[10px] px-2 py-0.5 rounded font-black', actionClass)}>{actionText}</span>
        </div>
        <div className="text-[10px] text-slate-500 mt-2">Stop ¥{formatPrice(position.stop_loss)}</div>
        <div className="text-[11px] text-slate-400 mt-2 max-w-[260px] leading-relaxed">{position.action_reason || '暂无明确动作，继续观察。'}</div>
      </td>
      <td className="px-6 py-5 text-right font-mono">
        <div className="text-sm font-bold">¥{formatPrice(position.current_price)}</div>
        <div className="text-[10px] text-slate-500">Buy ¥{formatPrice(position.buy_price)}</div>
      </td>
      <td className="px-6 py-5 text-right font-mono">
        <div className={cn('text-lg font-black', cnStockChange(position.pnl_pct))}>{formatPct(position.pnl_pct)}</div>
        <div className="text-[10px] text-slate-500">¥{position.pnl_amount > 0 ? '+' : ''}{formatPrice(position.pnl_amount)}</div>
      </td>
    </tr>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  required = false,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
      <input
        required={required}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="px-3 py-2 rounded-lg bg-white/5 border border-border-subtle outline-none text-sm text-slate-100 placeholder:text-slate-600"
      />
    </label>
  );
}

function StatCard({ label, value, subValue, color }: { label: string; value: string; subValue: string; color: string }) {
  return (
    <div className="glass-panel p-5 rounded-xl">
      <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-mono mb-2 block">{label}</span>
      <div className={cn('text-2xl font-black font-mono', color)}>{value}</div>
      <div className="text-[10px] text-slate-400 mt-1 uppercase font-mono">{subValue}</div>
    </div>
  );
}

function gradeClass(grade: WatchlistItem['buy_grade']) {
  if (grade === 'A') return 'bg-accent-green text-white';
  if (grade === 'B') return 'bg-accent-blue text-white';
  if (grade === 'SELL') return 'bg-accent-red text-white';
  if (grade === 'NONE') return 'bg-white/5 text-slate-500';
  return 'bg-accent-orange/20 text-accent-orange';
}
