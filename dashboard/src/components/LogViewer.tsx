import { useEffect, useRef } from "react";
import type { LogEntry } from "../types";
import { ScrollText } from "lucide-react";

interface LogViewerProps {
    logs: LogEntry[];
}

export function LogViewer({ logs }: LogViewerProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="rounded-xl border bg-card shadow-sm h-[300px] flex flex-col">
            <div className="p-4 border-b flex items-center gap-2">
                <ScrollText size={16} className="text-muted-foreground" />
                <h3 className="font-semibold text-sm">Live Logs</h3>
            </div>
            <div
                ref={scrollRef}
                className="flex-1 overflow-auto p-4 space-y-1 font-mono text-xs"
            >
                {logs.map((log, i) => (
                    <div key={i} className="text-muted-foreground break-all">
                        <span className="text-slate-600 mr-2">
                            [{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : "INFO"}]
                        </span>
                        <span className={
                            log.message.includes("ERROR") ? "text-red-400" :
                                log.message.includes("WARNING") ? "text-yellow-400" :
                                    log.message.includes("SIGNAL") ? "text-green-400" :
                                        "text-slate-300"
                        }>
                            {log.message}
                        </span>
                    </div>
                ))}
                {logs.length === 0 && (
                    <div className="text-center text-muted-foreground py-10 opacity-50">
                        Waiting for logs...
                    </div>
                )}
            </div>
        </div>
    );
}
