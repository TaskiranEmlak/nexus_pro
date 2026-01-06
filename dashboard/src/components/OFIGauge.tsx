import { cn } from '../lib/utils';

interface OFIGaugeProps {
    value: number; // -1 to +1
    symbol?: string;
}

export function OFIGauge({ value, symbol }: OFIGaugeProps) {
    // Clamp value between -1 and 1
    const clampedValue = Math.max(-1, Math.min(1, value));

    // Convert -1...+1 to 0...100 (percentage for rotation)
    const percentage = (clampedValue + 1) * 50;

    // Rotation: -90deg (full left) to +90deg (full right)
    const rotation = (clampedValue * 90);

    // Color based on value
    const getColor = () => {
        if (clampedValue > 0.3) return 'text-green-500';
        if (clampedValue < -0.3) return 'text-red-500';
        return 'text-yellow-500';
    };

    const getLabel = () => {
        if (clampedValue > 0.5) return 'STRONG BUY';
        if (clampedValue > 0.3) return 'BUY PRESSURE';
        if (clampedValue < -0.5) return 'STRONG SELL';
        if (clampedValue < -0.3) return 'SELL PRESSURE';
        return 'NEUTRAL';
    };

    return (
        <div className="rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-sm">Order Flow Imbalance</h3>
                {symbol && <span className="text-xs text-muted-foreground">{symbol}</span>}
            </div>

            {/* Gauge Container */}
            <div className="relative h-24 flex items-end justify-center overflow-hidden">
                {/* Background Arc */}
                <div className="absolute bottom-0 w-40 h-20 border-4 border-border rounded-t-full" />

                {/* Colored Zones */}
                <div className="absolute bottom-0 w-40 h-20">
                    <div className="absolute left-0 bottom-0 w-1/3 h-full bg-gradient-to-r from-red-500/20 to-transparent rounded-tl-full" />
                    <div className="absolute right-0 bottom-0 w-1/3 h-full bg-gradient-to-l from-green-500/20 to-transparent rounded-tr-full" />
                </div>

                {/* Needle */}
                <div
                    className="absolute bottom-0 left-1/2 origin-bottom transition-transform duration-300"
                    style={{ transform: `translateX(-50%) rotate(${rotation}deg)` }}
                >
                    <div className={cn("w-1 h-16 rounded-full", getColor(), "bg-current")} />
                    <div className={cn("w-3 h-3 rounded-full -mt-1 -ml-1", getColor(), "bg-current")} />
                </div>

                {/* Center Point */}
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-background border-2 border-border" />
            </div>

            {/* Value Display */}
            <div className="text-center mt-4">
                <div className={cn("text-2xl font-bold", getColor())}>
                    {(clampedValue * 100).toFixed(0)}%
                </div>
                <div className={cn("text-xs font-medium", getColor())}>
                    {getLabel()}
                </div>
            </div>

            {/* Labels */}
            <div className="flex justify-between text-xs text-muted-foreground mt-2 px-4">
                <span>SELL</span>
                <span>NEUTRAL</span>
                <span>BUY</span>
            </div>
        </div>
    );
}
