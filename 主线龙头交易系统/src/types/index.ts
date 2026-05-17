export interface MarketRisk {
  regime: 'risk_on' | 'neutral' | 'weak';
  breadth: number;
  index_above_ma20: boolean;
}

export interface MainlineSector {
  sector_name: string;
  mainline_score: number;
  mainline_status: 'rising' | 'continuing' | 'rotation' | 'fading' | 'risk';
  rank: number;
  limit_up_count: number;
  lianban_count: number;
  leader: string;
}

export interface StockFocus {
  symbol: string;
  name: string;
  sector: string;
  role: 'leader' | 'follower';
  stage: string;
  current_price: number;
  pct_chg: number;
  buy_grade: 'A' | 'B' | 'C' | 'NONE' | 'SELL';
  buy_score: number;
  strategy_name: string;
  action: 'buy' | 'sell' | 'hold' | 'reduce' | 'deny' | 'watch' | 'add';
  action_text: string;
  confidence: number;
  data_quality: 'full' | 'degraded' | 'mock';
  entry_price_low: number;
  entry_price_high: number;
  stop_loss_price: number;
  position_pct: number;
  sell_urgency: string;
  risk_warnings: string[];
  trend: {
    state: string;
    ma_alignment: string;
    slope_20: number;
  };
  volume_price: {
    volume_ratio: number;
    status: string;
  };
  sector_detail: {
    sector_score: number;
    mainline_status: string;
  };
  deny_result: string;
  llm_review: string;
}

export interface StrategySignalCandidate {
  symbol: string;
  name: string;
  sector: string;
  role: 'leader' | 'follower';
  strategy_name: string;
  action: 'buy' | 'sell' | 'hold' | 'reduce' | 'deny' | 'watch' | 'add';
  action_text: string;
  confidence: number;
  grade: 'A' | 'B' | 'C' | 'NONE' | 'SELL';
  is_focus: boolean;
  current_price: number;
  pct_chg: number;
  entry_price_low: number;
  entry_price_high: number;
  stop_loss_price: number;
  position_pct: number;
  sector_score: number;
  sector_status: string;
  data_quality: 'full' | 'degraded' | 'mock';
}

export interface EvaluationData {
  date: string;
  market_risk: MarketRisk;
  mainline_top5: MainlineSector[];
  focus_pool: StockFocus[];
  lianban_pool: LianbanCandidate[];
  strategy_signal_pool: StrategySignalCandidate[];
  sell_signals: any[];
  stage_denied: any[];
  observation_pool: any[];
}

export interface LianbanCandidate {
  symbol: string;
  name: string;
  lianban_count: number;
  limit_type: string;
  first_time: string;
  open_count: number;
  strategy_name: string;
  action: 'buy' | 'sell' | 'hold' | 'reduce' | 'deny' | 'watch' | 'add';
  grade: 'A' | 'B' | 'C' | 'NONE' | 'SELL';
  confidence: number;
  score: number;
  sector: string;
  stage: string;
  action_text: string;
}

export interface RadarSector {
  sector_name: string;
  radar_score: number;
  signal_type: string;
  stage_filter: string;
  reason: string[];
  suggested_watch: Array<{
    symbol: string;
    name: string;
    probability: number;
  }>;
}

export interface RiskWarning {
  target: string;
  target_type: 'stock' | 'sector';
  level: 'danger' | 'caution' | 'watch';
  signal_type: string;
  reason: string[];
  suggested_action: string;
}

export interface RadarData {
  date: string;
  mainline_radar: RadarSector[];
  risk_warnings: RiskWarning[];
}

export interface Position {
  symbol: string;
  name: string;
  buy_price: number;
  entry_date: string;
  quantity: number;
  current_price: number;
  pct_chg: number;
  stop_loss: number;
  hold_days: number;
  stage: string;
  trend_state: string;
  action_suggestion: 'hold' | 'reduce' | 'sell';
  action_reason?: string;
  market_value: number;
  pnl_amount: number;
  pnl_pct: number;
  notes: string;
}

export interface NewPositionInput {
  symbol: string;
  name?: string;
  entry_price: number;
  entry_date: string;
  quantity: number;
  stop_loss?: number;
  notes?: string;
}

export interface WatchlistItem {
  symbol: string;
  name: string;
  group: string;
  source: string;
  current_price: number;
  pct_chg: number;
  stage: string;
  buy_grade: 'A' | 'B' | 'C' | 'NONE' | 'SELL';
  strategy_name: string;
  action: 'buy' | 'sell' | 'hold' | 'reduce' | 'deny' | 'watch' | 'add';
  action_text: string;
  risk_warnings: string[];
}

export interface StrategyStat {
  strategy_name: string;
  total_signals: string | number;
  win_rate_1d: string | number;
  win_rate_3d: string | number;
  win_rate_5d: string | number;
  avg_return_1d: string | number;
  avg_return_3d: string | number;
  avg_return_5d: string | number;
  max_drawdown_5d: string | number;
  hit_stop_loss_rate: string | number;
}

export interface BacktestData {
  strategy_stats: StrategyStat[];
  stage_stats: Array<Record<string, string | number>>;
}
