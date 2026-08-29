'use client'

import { ImageLab } from '@/components/ImageLab'

export default function StudioView({ isMobile }: { isMobile: boolean }) {
  const pad = isMobile
    ? '16px 12px calc(var(--bottom-nav-height) + 32px)'
    : '24px 32px 48px'

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        minWidth: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: pad,
      }}
    >
      <div style={{ width: '100%', maxWidth: 1240, margin: '0 auto', minWidth: 0 }}>
        <ImageLab compact={isMobile} />
      </div>
    </div>
  )
}
