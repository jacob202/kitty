'use client'

import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { fetchPerfStats, type PerfStats } from '@/lib/gateway'

export function PerfDashboard() {
  const [stats, setStats] = useState<PerfStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
    const interval = setInterval(loadStats, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  async function loadStats() {
    try {
      const data = await fetchPerfStats(24)
      setStats(data)
    } catch (e) {
      console.error('Failed to load perf stats:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div style={containerStyle}>Loading performance stats...</div>
  }

  if (!stats) {
    return <div style={containerStyle}>No performance data available</div>
  }

  return (
    <div style={containerStyle}>
      <h3 style={titleStyle}>Performance (24h)</h3>
      
      <div style={gridStyle}>
        <StatBox label="Requests" value={stats.total_requests.toString()} color="var(--mint)" />
        <StatBox label="Avg Latency" value={`${stats.avg_latency_ms.toFixed(0)}ms`} color="var(--teal)" />
        <StatBox label="Max Latency" value={`${stats.max_latency_ms.toFixed(0)}ms`} color="var(--yellow)" />
        <StatBox label="Total Tokens" value={stats.total_tokens.toLocaleString()} color="var(--purple)" />
        <StatBox label="Avg Tokens" value={stats.avg_tokens.toFixed(0)} color="var(--blue)" />
        <StatBox label="Active Schedules" value={stats.active_schedules.toString()} color="var(--pink)" />
      </div>

      {stats.schedules && stats.schedules.length > 0 && (
        <div style={schedulesStyle}>
          <h4 style={subtitleStyle}>Scheduled Jobs</h4>
          {stats.schedules.map((sched) => (
            <div key={sched.id} style={scheduleRowStyle}>
              <span style={scheduleNameStyle}>{sched.name}</span>
              <span style={scheduleStatusStyle}>{sched.enabled ? '✓' : '✗'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ ...statBoxStyle, borderColor: color }}>
      <div style={statLabelStyle}>{label}</div>
      <div style={{ ...statValueStyle, color }}>{value}</div>
    </div>
  )
}

const containerStyle: CSSProperties = {
  padding: '16px',
  background: 'var(--surface-low)',
  borderRadius: '8px',
  border: '1px solid var(--border)',
}

const titleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '11px',
  fontWeight: 700,
  color: 'var(--text-ghost)',
  letterSpacing: '0.16em',
  textTransform: 'lowercase',
  marginBottom: '12px',
}

const subtitleStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '9px',
  fontWeight: 600,
  color: 'var(--text-ghost)',
  letterSpacing: '0.12em',
  textTransform: 'lowercase',
  marginTop: '16px',
  marginBottom: '8px',
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: '8px',
}

const statBoxStyle: CSSProperties = {
  background: 'var(--surface-high)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  padding: '10px 8px',
  textAlign: 'center',
}

const statLabelStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '8px',
  color: 'var(--text-ghost)',
  letterSpacing: '0.14em',
  textTransform: 'lowercase',
  marginBottom: '4px',
}

const statValueStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '16px',
  fontWeight: 700,
  lineHeight: 1,
}

const schedulesStyle: CSSProperties = {
  marginTop: '16px',
  paddingTop: '12px',
  borderTop: '1px solid var(--border)',
}

const scheduleRowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '6px 0',
  borderBottom: '1px solid var(--border-dim)',
}

const scheduleNameStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '10px',
  color: 'var(--text)',
}

const scheduleStatusStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '12px',
  color: 'var(--mint)',
}
