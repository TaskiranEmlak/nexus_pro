export interface Signal {
    symbol: string;
    type: "BUY" | "SELL";
    confidence: number;
    regime: string;
    entry: number;
    sl: number;
    tp: number;
    reason: string;
    timestamp: string;
}

export interface DailyStats {
    date: string;
    trades: number;
    wins: number;
    losses: number;
    win_rate: number;
    pnl: number;
    drawdown: number;
    open_positions: number;
    is_paused: boolean;
    signals_today?: number;
}

export interface LogEntry {
    message: string;
    timestamp?: string;
}
