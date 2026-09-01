'use client'

import type { GatewayLoop } from '@/lib/gateway'
import { CronPanel } from './CronPanel'
import { LoopWatch } from './LoopWatch'
import { MonitorPanel } from './MonitorPanel'

interface Props {
  isMobile: boolean
  loops: GatewayLoop[]
  loopsLoading: boolean
  loopsError?: string | null
  onLoopToggle: (id: string) => void
  selectedRunId?: string | null
}

export default function AutomationsView({ isMobile, loops, loopsLoading, loopsError, onLoopToggle, selectedRunId = null }: Props) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '16px 12px 124px' : '24px 32px 40px' }}>
      <div style={{ width: '100%', maxWidth: 1120, margin: '0 auto', display: 'grid', gap: 24 }}>
        <header style={{ display: 'grid', gap: 6 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: isMobile ? 28 : 32, color: 'var(--color-text-primary)' }}>
            Automations
          </h1>
          <p style={{ margin: 0, maxWidth: 680, color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.55 }}>
            What Kitty runs on a schedule, what is paused, and what needs attention.
          </p>
        </header>

        <section aria-labelledby="automation-schedules-heading" style={{ display: 'grid', gap: 10 }}>
          <h2 id="automation-schedules-heading" style={sectionHeadingStyle}>Schedules</h2>
          <CronPanel variant="full" isMobile={isMobile} selectedRunId={selectedRunId} />
        </section>

        <section aria-labelledby="automation-routines-heading" style={{ display: 'grid', gap: 10 }}>
          <h2 id="automation-routines-heading" style={sectionHeadingStyle}>Background routines</h2>
          {loopsError ? (
            <div style={errorNoticeStyle}>Background routines are unavailable right now.</div>
          ) : (
            <LoopWatch
              loops={loops}
              onToggle={onLoopToggle}
              title=""
              isLoading={loopsLoading}
            />
          )}
        </section>

        <section aria-labelledby="automation-monitors-heading" style={{ display: 'grid', gap: 10 }}>
          <h2 id="automation-monitors-heading" style={sectionHeadingStyle}>Monitors</h2>
          <MonitorPanel />
        </section>
      </div>
    </div>
  )
}

const sectionHeadingStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-display)',
  fontSize: 18,
  color: 'var(--color-text-primary)',
}

const errorNoticeStyle: React.CSSProperties = { padding: '14px 16px', background: 'var(--color-surface)', border: '1px solid var(--color-separator)', borderRadius: 'var(--r-surface)', color: 'var(--color-text-secondary)', fontSize: 14 }
