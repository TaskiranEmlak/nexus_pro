import { useEffect, useState } from 'react';
import { SignalCard } from './components/SignalCard';
import { StatsPanel } from './components/StatsPanel';
import { LogViewer } from './components/LogViewer';
import type { Signal, DailyStats, LogEntry } from './types';
import { Terminal, Zap } from 'lucide-react';

function App() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<DailyStats>({
    date: new Date().toISOString().split('T')[0],
    trades: 0,
    wins: 0,
    losses: 0,
    win_rate: 0,
    pnl: 0,
    drawdown: 0,
    open_positions: 0,
    is_paused: false,
    signals_today: 0
  });

  const [status, setStatus] = useState("disconnected");

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');

      ws.onopen = () => {
        setStatus("connected");
        // Initial log
        setLogs(prev => [...prev, { message: "Connected to Nexus Pro Core", timestamp: new Date().toISOString() }]);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'SIGNAL') {
            setSignals(prev => [message.data, ...prev].slice(0, 50)); // Keep last 50
          } else if (message.type === 'STATS') {
            setStats(message.data);
          } else if (message.type === 'LOG') {
            setLogs(prev => [...prev, { ...message.data, timestamp: message.timestamp }].slice(-100)); // Keep last 100
          }
        } catch (e) {
          console.error("Parse error", e);
        }
      };

      ws.onclose = () => {
        setStatus("disconnected");
        setLogs(prev => [...prev, { message: "Disconnected. Reconnecting...", timestamp: new Date().toISOString() }]);
        setTimeout(connect, 3000);
      };

      return ws;
    };

    const ws = connect();
    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground p-6 font-sans">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-border/40 pb-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary flex items-center justify-center text-primary-foreground shadow-lg shadow-primary/20">
              <Zap className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Nexus Pro</h1>
              <p className="text-sm text-muted-foreground">AI-Powered High Frequency Trading</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-secondary text-xs font-medium">
              <div className={`h-2 w-2 rounded-full ${status === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {status === 'connected' ? 'SYSTEM ONLINE' : 'OFFLINE'}
            </div>
          </div>
        </header>

        {/* Stats */}
        <StatsPanel stats={stats} />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Signals Feed (Main Column) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold tracking-tight">Live Signals</h2>
              <span className="text-xs text-muted-foreground">{signals.length} signals generated</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {signals.length === 0 ? (
                <div className="col-span-full py-20 text-center border-2 border-dashed border-border/50 rounded-xl">
                  <p className="text-muted-foreground">Waiting for market signals...</p>
                  <p className="text-xs text-muted-foreground mt-2">AI is monitoring 50+ pairs</p>
                </div>
              ) : (
                signals.map((signal, i) => (
                  <SignalCard key={i} signal={signal} />
                ))
              )}
            </div>
          </div>

          {/* Sidebar (Logs & Controls) */}
          <div className="space-y-6">
            {/* Terminal */}
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                <Terminal size={18} />
                System Logs
              </h2>
            </div>
            <LogViewer logs={logs} />

            {/* Quick Actions (Placeholder) */}
            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <h3 className="font-semibold text-sm mb-4">Quick Actions</h3>
              <div className="grid grid-cols-2 gap-2">
                <button className="px-4 py-2 bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-lg text-sm font-medium transition-colors">
                  Emergency Stop
                </button>
                <button className="px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-lg text-sm font-medium transition-colors">
                  Clear Logs
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
