'use client'

import { ImageLab } from '@/components/ImageLab'

export default function StudioView({ isMobile }: { isMobile: boolean }) {
  const pad = isMobile ? '16px 12px 124px' : '24px 32px 40px'

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: pad,
      }}
    >
      <ImageLab compact={isMobile} />
    </div>
  )
}
