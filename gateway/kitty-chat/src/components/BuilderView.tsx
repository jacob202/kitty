'use client'
import { BuilderCockpit } from '@/components/builder/BuilderCockpit'

export default function BuilderView({ onBack }: { onBack?: () => void }) {
  return <BuilderCockpit onBack={onBack} />
}
