'use client'
import { BuilderPanel } from '@/components/BuilderSurface'

export default function BuilderView({ onBack }: { onBack?: () => void }) {
  return <BuilderPanel onBack={onBack} />
}
