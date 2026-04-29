"use client";

import React, { useState, useEffect } from 'react';
import { AlertTriangle, Minus, RefreshCw, TrendingDown, TrendingUp, XCircle } from 'lucide-react';

interface FailedCheck {
  name: string;
  reason?: string;
}

interface EvalRun {
  run_id: string;
  suite: string;
  artifact?: string;
  started_at?: number | null;
  score: {
    passed: number;
    total: number;
    rate: number;
  };
  failed_checks: Array<FailedCheck | string>;
}

interface EvalData {
  ok: boolean;
  dashboard?: {
    artifact_count: number;
    corrupt_count: number;
    parsed_count: number;
    latest?: EvalRun | null;
    trend?: {
      direction: 'up' | 'down' | 'flat' | 'unknown';
      delta: number | null;
      previous_run_id: string | null;
    };
    recent: EvalRun[];
  };
}

function formatRunDate(startedAt?: number | null) {
  if (typeof startedAt !== 'number') return 'Unknown';
  return new Date(startedAt * 1000).toLocaleString();
}

function formatFailedCheck(check: FailedCheck | string) {
  if (typeof check === 'string') return check;
  const reason = check.reason ? `: ${check.reason}` : '';
  return `${check.name}${reason}`;
}

function TrendIcon({ direction }: { direction?: 'up' | 'down' | 'flat' | 'unknown' }) {
  if (direction === 'up') return <TrendingUp size={28} aria-hidden="true" />;
  if (direction === 'down') return <TrendingDown size={28} aria-hidden="true" />;
  return <Minus size={28} aria-hidden="true" />;
}

export default function EvalDashboard() {
  const [data, setData] = useState<EvalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const backendHost = window.location.hostname;
      const response = await fetch(`http://${backendHost}:5001/api/eval/dashboard`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const result: EvalData = await response.json();
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load eval dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full text-sm opacity-50">
        <div className="animate-pulse">Loading Eval Data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full text-red-400 gap-4 p-4">
        <AlertTriangle size={28} aria-hidden="true" />
        <p className="text-sm font-mono">{error}</p>
        <button onClick={fetchDashboard} className="text-xs underline opacity-80 hover:opacity-100 mt-2">Retry</button>
      </div>
    );
  }

  if (!data?.dashboard) {
    return <div className="flex-1 p-8 text-sm opacity-50">No eval data available.</div>;
  }

  const { dashboard } = data;
  const latest = dashboard.latest;
  const trend = dashboard.trend;
  const trendColor = trend?.direction === 'up' ? 'text-green-400' : trend?.direction === 'down' ? 'text-red-400' : 'opacity-60';

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--panel-bg)] overflow-y-auto no-scrollbar p-4 md:p-8">
      <div className="max-w-4xl mx-auto w-full space-y-8">
        <header className="flex justify-between items-end border-b border-[var(--border-color)] pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tighter" style={{ color: 'var(--accent-color)' }}>
              EVAL DASHBOARD
            </h1>
            <p className="text-sm opacity-60 font-mono mt-1">
              {dashboard.artifact_count} artifacts total ({dashboard.corrupt_count} corrupt)
            </p>
          </div>
          <button 
            onClick={fetchDashboard}
            className="inline-flex items-center gap-2 text-xs px-3 py-1 rounded border border-[var(--border-color)] hover:bg-white hover:bg-opacity-5 transition-colors"
          >
            <RefreshCw size={12} aria-hidden="true" />
            Refresh
          </button>
        </header>

        {latest ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg border border-[var(--border-color)] bg-black bg-opacity-20 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest opacity-50">Latest Pass Rate</span>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-light">{(latest.score.rate * 100).toFixed(1)}%</span>
                <span className="text-xs opacity-60 pb-1">({latest.score.passed}/{latest.score.total})</span>
              </div>
            </div>

            <div className="p-4 rounded-lg border border-[var(--border-color)] bg-black bg-opacity-20 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest opacity-50">Trend</span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className={`font-light ${trendColor}`}>
                  <TrendIcon direction={trend?.direction} />
                </span>
                {trend && trend.delta !== null && trend.delta !== 0 && (
                  <span className="text-sm opacity-60 pb-1">
                    {trend.delta > 0 ? '+' : ''}{(trend.delta * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>

            <div className="p-4 rounded-lg border border-[var(--border-color)] bg-black bg-opacity-20 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest opacity-50">Latest Run</span>
              <div className="mt-2 text-sm font-mono opacity-80 break-all">
                {latest.run_id} ({latest.suite})
              </div>
              <div className="text-[10px] opacity-40 mt-auto pt-2">
                {formatRunDate(latest.started_at)}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-lg border border-[var(--border-color)] bg-black bg-opacity-20 text-center opacity-50 text-sm">
            No recent runs found.
          </div>
        )}

        {latest && latest.failed_checks && latest.failed_checks.length > 0 && (
          <div className="mt-6 border border-red-500 border-opacity-30 rounded-lg overflow-hidden">
            <div className="bg-red-500 bg-opacity-10 px-4 py-2 border-b border-red-500 border-opacity-20">
              <h3 className="text-xs font-bold text-red-400 uppercase tracking-wider">Failed Checks</h3>
            </div>
            <ul className="p-4 space-y-2 text-sm font-mono bg-black bg-opacity-40">
              {latest.failed_checks.map((check, idx) => (
                <li key={idx} className="flex items-start gap-2 text-red-300">
                  <XCircle size={14} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
                  <span>{formatFailedCheck(check)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-8">
          <h2 className="text-sm font-bold uppercase tracking-widest opacity-50 mb-4 border-b border-[var(--border-color)] pb-2">Recent Runs</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="opacity-40 border-b border-[var(--border-color)]">
                  <th className="pb-2 font-normal">Run ID</th>
                  <th className="pb-2 font-normal">Suite</th>
                  <th className="pb-2 font-normal">Rate</th>
                  <th className="pb-2 font-normal">Date</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.recent.slice(0, 10).map((run) => (
                  <tr key={run.run_id} className="border-b border-[var(--border-color)] border-opacity-50 hover:bg-white hover:bg-opacity-5">
                    <td className="py-2 opacity-80">{run.run_id}</td>
                    <td className="py-2 opacity-60">{run.suite}</td>
                    <td className="py-2">
                      <span className={run.score.rate === 1 ? 'text-green-400' : 'text-red-400'}>
                        {(run.score.rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 opacity-40">
                      {formatRunDate(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
