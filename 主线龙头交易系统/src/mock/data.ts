import { EvaluationData, RadarData, Position } from '../types';

export const MOCK_EVALUATION: EvaluationData = {
  date: "2026-05-16",
  market_risk: {
    regime: "risk_on",
    breadth: 0.65,
    index_above_ma20: true
  },
  mainline_top5: [
    {
      sector_name: "AI算力",
      mainline_score: 82,
      mainline_status: "rising",
      rank: 1,
      limit_up_count: 5,
      lianban_count: 2,
      leader: "海康威视"
    },
    {
      sector_name: "固态电池",
      mainline_score: 75,
      mainline_status: "continuing",
      rank: 2,
      limit_up_count: 3,
      lianban_count: 1,
      leader: "赣锋锂业"
    },
    {
      sector_name: "智能驾驶",
      mainline_score: 68,
      mainline_status: "rotation",
      rank: 3,
      limit_up_count: 2,
      lianban_count: 1,
      leader: "赛力斯"
    }
  ],
  focus_pool: [
    {
      symbol: "002415.SZ",
      name: "海康威视",
      sector: "AI算力",
      role: "leader",
      stage: "stage_2_rising",
      current_price: 38.50,
      pct_chg: 2.35,
      buy_grade: "A",
      buy_score: 85,
      strategy_name: "leader_breakout",
      action: "buy",
      action_text: "突破确认，板块共振，可半仓介入",
      confidence: 0.78,
      data_quality: "full",
      entry_price_low: 37.50,
      entry_price_high: 38.80,
      stop_loss_price: 36.50,
      position_pct: 0.15,
      sell_urgency: "无",
      risk_warnings: [],
      trend: {
        "state": "strong_up",
        "ma_alignment": "多头排列",
        "slope_20": 0.032
      },
      volume_price: {
        "volume_ratio": 1.8,
        "status": "healthy"
      },
      sector_detail: {
        "sector_score": 82,
        "mainline_status": "rising"
      },
      deny_result: "pass",
      llm_review: "分歧后放量突破，主升延续概率高"
    },
    {
      symbol: "002460.SZ",
      name: "赣锋锂业",
      sector: "固态电池",
      role: "leader",
      stage: "stage_1_init",
      current_price: 42.15,
      pct_chg: 5.12,
      buy_grade: "B",
      buy_score: 72,
      strategy_name: "oversold_rebound",
      action: "hold",
      action_text: "首板确立，观察持续性",
      confidence: 0.65,
      data_quality: "full",
      entry_price_low: 41.00,
      entry_price_high: 42.50,
      stop_loss_price: 39.80,
      position_pct: 0.05,
      sell_urgency: "无",
      risk_warnings: ["上方套牢盘较多"],
      trend: {
        "state": "rebound",
        "ma_alignment": "均线缠绕",
        "slope_20": 0.015
      },
      volume_price: {
        "volume_ratio": 2.5,
        "status": "explosive"
      },
      sector_detail: {
        "sector_score": 75,
        "mainline_status": "continuing"
      },
      deny_result: "pass",
      llm_review: "行业基本面见底，机构回补迹象明显"
    }
  ],
  lianban_pool: [
    {
      symbol: "002460.SZ",
      name: "赣锋锂业",
      lianban_count: 2,
      limit_type: "涨停",
      first_time: "09:35",
      open_count: 2,
      strategy_name: "lianban_leader_template",
      action: "watch",
      grade: "C",
      confidence: 0.55,
      score: 62,
      sector: "小金属",
      stage: "stage_1_start",
      action_text: "连板高度2，等待竞价和阶段确认"
    }
  ],
  strategy_signal_pool: [],
  sell_signals: [
    {
      symbol: "601127.SH",
      name: "赛力斯",
      reason: "高位放量阴线",
      suggested_action: "减仓"
    }
  ],
  stage_denied: [],
  observation_pool: []
};

export const MOCK_RADAR: RadarData = {
  date: "2026-05-16",
  mainline_radar: [
    {
      sector_name: "低空经济",
      radar_score: 72,
      signal_type: "limit_up_cluster",
      stage_filter: "stage_1",
      reason: ["板块内出现3只涨停", "成交额放大80%"],
      suggested_watch: [
        {"symbol": "000099.SZ", "name": "中信海直", "probability": 0.82},
        {"symbol": "300011.SZ", "name": "鼎捷软件", "probability": 0.75}
      ]
    }
  ],
  risk_warnings: [
    {
      target: "高位股",
      target_type: "sector",
      level: "danger",
      signal_type: "overflow_risk",
      reason: ["连板高度下降", "亏钱效应扩散"],
      suggested_action: "空仓或极轻仓"
    },
    {
      target: "中际旭创",
      target_type: "stock",
      level: "caution",
      signal_type: "divergence",
      reason: ["缩量过顶", "卖点出现"],
      suggested_action: "分批获利了结"
    }
  ]
};

export const MOCK_POSITIONS: Position[] = [
  {
    symbol: "002415.SZ",
    name: "海康威视",
    buy_price: 36.80,
    entry_date: "2026-05-14",
    quantity: 1000,
    current_price: 38.50,
    pct_chg: 4.62,
    stop_loss: 36.50,
    hold_days: 3,
    stage: "stage_2",
    trend_state: "uping",
    action_suggestion: "hold",
    market_value: 38500,
    pnl_amount: 1700,
    pnl_pct: 4.62,
    notes: ""
  }
];
