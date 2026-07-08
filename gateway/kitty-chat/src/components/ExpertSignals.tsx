'use client'
import React, { useCallback, useState, type CSSProperties } from 'react'
import {
  useExpertSignals,
  useDismissExpertSignal,
  useSnoozeExpert,
} from '@/lib/queries'
import { Card, CardHeader, ItemCard } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Skeleton } from './Skeleton'

export function ExpertSignals() {
  const { data: signals = [], isError, isLoading } = useExpertSignals()
  const dismissSignal = useDismissExpertSignal()
  const snoozeExpert = useSnoozeExpert()
  const [snoozedExperts, setSnoozedExperts] = useState<Set<string>>(new Set())

  const handleDismiss = useCallback(
    (signalId: number) => {
      dismissSignal.mutate(signalId)
    },
    [dismissSignal]
  )

  const handleSnooze = useCallback(
    (expertId: string) => {
      // 24 hours snooze
      snoozeExpert.mutate({ expertId, durationHours: 24 })
      setSnoozedExperts((prev) => new Set(prev).add(expertId))
    },
    [snoozeExpert]
  )

  // Filter out signals from locally snoozed experts (optimistic visual update)
  const visibleSignals = signals.filter(
    (s) => !snoozedExperts.has(s.source.replace('expert.', ''))
  )

  if (isError) return null

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <CardHeader title="Expert Signals" count={`${visibleSignals.length} new`} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {visibleSignals.map((sig) => {
          const expertName = sig.source.replace('expert.', '')
          const { headline, analysis } = sig.payload

          return (
            <ItemCard key={sig.id} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--orange)' }}>
                  {expertName}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <Button
                    variant="action"
                    onClick={() => handleSnooze(expertName)}
                    ariaLabel="Snooze this expert for 24h"
                    disabled={snoozeExpert.isPending}
                  >
                    Snooze 24h
                  </Button>
                  <Button
                    variant="action"
                    onClick={() => handleDismiss(sig.id)}
                    ariaLabel="Dismiss this signal"
                    disabled={dismissSignal.isPending}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>

              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 13, fontWeight: 600, color: 'var(--text)', marginTop: 2 }}>
                {headline}
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
                {analysis}
              </div>
            </ItemCard>
          )
        })}
        {visibleSignals.length === 0 && (
          isLoading ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <Skeleton height={56} />
              <Skeleton height={56} />
            </div>
          ) : (
            <EmptyState>No unprocessed signals</EmptyState>
          )
        )}
      </div>
    </Card>
  )
}
