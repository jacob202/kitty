'use client'
import { BuilderCockpit } from '@/components/builder/BuilderCockpit'

export default function BuilderView({ onBack, isMobile = false }: { onBack?: () => void; isMobile?: boolean }) {
  return <BuilderCockpit onBack={onBack} isMobile={isMobile} />
}
