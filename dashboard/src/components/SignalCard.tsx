import type { Signal } from "../types";
import { ArrowUpCircle, ArrowDownCircle, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "../lib/utils";

interface SignalCardProps {
    signal: Signal;
}

export function SignalCard({ signal }: SignalCardProps) {
    const isBuy = signal.type === "BUY";

    return (
        <div className={cn(
            "relative overflow-hidden rounded-xl border p-4 shadow-sm transition-all hover:shadow-md",
            "bg-card text-card-foreground",
            isBuy ? "border-green-900/50 hover:border-green-500/50" : "border-red-900/50 hover:border-red-500/50"
        )}>
            {/* Background Glow */}
            <div className={cn(
                "absolute -right-12 -top-12 h-24 w-24 rounded-full blur-3xl opacity-20",
                isBuy ? "bg-green-500" : "bg-red-500"
            )} />

            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <div className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-full border bg-background/50 backdrop-blur",
                        isBuy ? "border-green-500/30 text-green-500" : "border-red-500/30 text-red-500"
                    )}>
                        {isBuy ? <ArrowUpCircle size={20} /> : <ArrowDownCircle size={20} />}
                    </div>
                    <div>
                        <h3 className="font-bold tracking-tight text-lg">{signal.symbol}</h3>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                            {new Date(signal.timestamp).toLocaleTimeString()}
                            <span className="inline-block h-1 w-1 rounded-full bg-slate-600" />
                            {signal.regime}
                        </p>
                    </div>
                </div>

                <div className="flex flex-col items-end">
                    <div className={cn(
                        "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium border",
                        signal.confidence >= 80
                            ? "border-green-500/30 bg-green-500/10 text-green-400"
                            : "border-yellow-500/30 bg-yellow-500/10 text-yellow-400"
                    )}>
                        {signal.confidence >= 80 ? <CheckCircle2 size={10} /> : <AlertTriangle size={10} />}
                        {signal.confidence}% Conf.
                    </div>
                </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                <div className="rounded-lg bg-secondary/50 p-2 text-center">
                    <span className="text-[10px] uppercase text-muted-foreground">Entry</span>
                    <div className="font-mono font-medium text-foreground">{signal.entry}</div>
                </div>
                <div className="rounded-lg bg-green-950/20 p-2 text-center border border-green-900/20">
                    <span className="text-[10px] uppercase text-green-500/70">Target</span>
                    <div className="font-mono font-medium text-green-400">{signal.tp}</div>
                </div>
                <div className="rounded-lg bg-red-950/20 p-2 text-center border border-red-900/20">
                    <span className="text-[10px] uppercase text-red-500/70">Stop</span>
                    <div className="font-mono font-medium text-red-400">{signal.sl}</div>
                </div>
            </div>

            <div className="mt-3 border-t border-border/50 pt-2">
                <p className="text-xs text-muted-foreground italic truncate">
                    "{signal.reason}"
                </p>
            </div>
        </div>
    );
}
