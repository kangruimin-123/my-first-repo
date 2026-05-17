import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(price: number) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price);
}

export function formatPct(pct: number) {
  return `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`;
}

export function cnStockChange(value: number) {
  if (value > 0) return 'text-accent-red';
  if (value < 0) return 'text-accent-green';
  return 'text-slate-400';
}

const STRATEGY_LABELS: Record<string, string> = {
  leader_pullback: '龙头回踩低吸',
  leader_breakout: '龙头突破确认',
  leader_first_divergence: '龙头首次分歧',
  leader_trend_continue: '龙头趋势延续',
  leader_reseal: '龙头炸板回封',
  core_mid_trend_pullback: '趋势中军回踩',
  elastic_breakout: '弹性票突破',
  panic_reversal: '恐慌反转',
  auction_relative_strength: '竞价相对强度',
  lianban_leader_template: '连板龙头模板',
  mainline_switch: '主线切换',
  trend_hold: '趋势持仓',
  oversold_rebound: '超跌反弹',
};

const STAGE_LABELS: Record<string, string> = {
  stage_0_accumulation: '底部蓄势',
  stage_1_start: '启动初期',
  stage_1_init: '启动初期',
  stage_2_rising: '主升阶段',
  stage_3_distribution: '高位分歧',
  stage_4_decline: '下跌退潮',
  stage_0: '底部蓄势',
  stage_1: '启动初期',
  stage_2: '主升阶段',
  stage_3: '高位分歧',
  stage_4: '下跌退潮',
};

const ACTION_LABELS: Record<string, string> = {
  buy: '买入',
  watch: '观察',
  add: '加仓',
  hold: '持有',
  reduce: '减仓',
  sell: '卖出',
  deny: '禁止买入',
};

export function strategyLabel(value: string) {
  if (!value) return '暂无策略';
  return STRATEGY_LABELS[value] || value;
}

export function stageLabel(value: string) {
  if (!value) return '阶段未知';
  return STAGE_LABELS[value] || value;
}

export function actionLabel(value: string) {
  if (!value) return '无动作';
  return ACTION_LABELS[value] || value;
}

export function readableActionText(value: string) {
  if (!value) return '观察中：暂未触发买入、加仓、减仓或卖出条件';
  return value
    .replaceAll('阶段门控禁止买入', '阶段门控拦截：当前阶段不适合买入')
    .replaceAll('stage_0_accumulation', stageLabel('stage_0_accumulation'))
    .replaceAll('stage_1_start', stageLabel('stage_1_start'))
    .replaceAll('stage_2_rising', stageLabel('stage_2_rising'))
    .replaceAll('stage_3_distribution', stageLabel('stage_3_distribution'))
    .replaceAll('stage_4_decline', stageLabel('stage_4_decline'))
    .replaceAll('risk level high', '高风险')
    .replaceAll('风险等级 high', '风险等级：高')
    .replaceAll('风险等级 critical', '风险等级：极高');
}
