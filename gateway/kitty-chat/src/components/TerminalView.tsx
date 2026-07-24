'use client'
import { TerminalStrip } from '@/components/TerminalStrip'

export default function TerminalView({ isMobile }: { isMobile: boolean }) {
  return (
    <div style={{
      flex: 1,
      padding: isMobile ? '16px 12px 124px' : '24px 32px 40px',
      display: 'flex', flexDirection: 'column',
    }}>
      <TerminalStrip title="gateway log" maxLines={100} />
    </div>
  )
}
