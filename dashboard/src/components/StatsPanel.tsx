import type { DailyStats } from "../types";
import { TrendingUp, TrendingDown, Activity, Wallet, ShieldCheck } from "lucide-react";
import { cn } from "../lib/utils";

interface StatsPanelProps {
    stats: DailyStats;
}

export function StatsPanel({ stats }: StatsPanelProps) {
    const isProfitable = stats.pnl >= 0;

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* PnL Card */}
            <div className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-muted-foreground">Daily PnL</p>
                    {isProfitable ? (
                        <TrendingUp className="h-4 w-4 text-green-500" />
                    ) : (
                        <TrendingDown className="h-4 w-4 text-red-500" />
                    )}
                </div>
                <div className={cn("text-2xl font-bold", isProfitable ? "text-green-500" : "text-red-500")}>
                    {stats.pnl > 0 ? "+" : ""}{stats.pnl.toFixed(2)} USDT
                </div>
                <p className="text-xs text-muted-foreground">
                    {stats.trades} trades today
                </p>
            </div>

            {/* Win Rate Card */}
            <div className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-muted-foreground">Win Rate</p>
                    <Activity className="h-4 w-4 text-blue-500" />
                </div>
                <div className="text-2xl font-bold text-foreground">
                    {(stats.win_rate * 100).toFixed(1)}%
                </div>
                <p className="text-xs text-muted-foreground">
                    {stats.wins}W - {stats.losses}L
                </p>
            </div>

            {/* Signals Card */}
            <div className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-muted-foreground">Signals Generated</p>
                    <Wallet className="h-4 w-4 text-purple-500" />
                </div>
                <div className="text-2xl font-bold text-foreground">
                    {stats.signals_today || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                    Target: 100/day
                </p>
            </div>

            {/* Risk Card */}
            <div className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-muted-foreground">Risk Status</p>
                    <ShieldCheck className={cn("h-4 w-4", stats.is_paused ? "text-red-500" : "text-green-500")} />
                </div>
                <div className={cn("text-2xl font-bold", stats.is_paused ? "text-red-500" : "text-green-500")}>
                    {stats.is_paused ? "PAUSED" : "ACTIVE"}
                </div>
                <p className="text-xs text-muted-foreground">
                    DD: -{stats.drawdown.toFixed(2)}
                </p>
            </div>
        </div>
    );
}
