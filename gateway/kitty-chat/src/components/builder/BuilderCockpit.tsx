'use client'

import { useMemo, useState, type CSSProperties } from 'react'
import { useGatewayRuntimeManifest } from '@/lib/queries'
import { ArrowLeft, Grid, List } from 'lucide-react'
import { BuilderPacketTree } from './BuilderPacketTree'
import { WorkerPane } from './BuilderWorkerPane'
import { WorkerInspector } from './BuilderWorkerInspector'
import { OperatorControls } from './OperatorControls'
import type { BuilderStatusSnapshot, BuilderPacketStatus } from '@/lib/gateway'

const cockpitRoot: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(220px, 280px) 1fr',
  gridTemplateRows: '1fr',
  height: '100%',
  maxWidth: 1400,
  margin: '0 auto',
  gap: 0,
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  overflow: 'hidden',
  background: 'var(--color-surface)',
  boxSizing: 'border-box',
}

const withInspector: CSSProperties = {
  ...cockpitRoot,
  gridTemplateColumns: 'minmax(200px, 260px) 1fr minmax(220px, 300px)',
}

const mobileRoot: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  maxWidth: 600,
  margin: '0 auto',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-surface)',
  overflow: 'hidden',
  background: 'var(--color-surface)',
}

const panelBase: CSSProperties = {
  borderRight: '1px solid var(--color-separator)',
  overflow: 'auto',
  minHeight: 0,
}

const toolbarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '6px 12px',
  borderBottom: '1px solid var(--line)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--color-text-secondary)',
}

const toolbarButton: CSSProperties = {
  background: 'none',
  border: '1px solid var(--color-separator)',
  borderRadius: 'var(--r-control)',
  minHeight: 36,
  padding: '6px 10px',
  cursor: 'pointer',
  color: 'var(--color-text-primary)',
  fontFamily: 'var(--font-body)',
  fontSize: 12,
  display: 'flex',
  alignItems: 'center',
  gap: 4,
}

const activeTab: CSSProperties = {
  ...toolbarButton,
  background: 'var(--color-selected)',
  borderColor: 'var(--color-accent)',
}


const mobileSurfaceHeader: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  alignItems: 'center',
  gap: '4px 10px',
  padding: '10px 12px',
  borderBottom: '1px solid var(--color-separator)',
  background: 'var(--color-surface)',
}

const mobileBackButton: CSSProperties = {
  minHeight: 44,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '0 4px',
  color: 'var(--color-text-secondary)',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  background: 'transparent',
}

const mobileTabBar: CSSProperties = {
  display: 'flex',
  borderBottom: '1px solid var(--color-separator)',
  background: 'var(--color-surface)',
}

const mobileTitleStyle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-display)',
  fontSize: 18,
  color: 'var(--color-text-primary)',
}

const mobileStatusStyle: CSSProperties = {
  gridColumn: '1 / -1',
  color: 'var(--color-text-muted)',
  fontFamily: 'var(--font-body)',
  fontSize: 12,
}

const mobileTab: CSSProperties = {
  flex: 1,
  minHeight: 44,
  padding: '10px 8px',
  textAlign: 'center',
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  borderBottom: '2px solid transparent',
}

const mobileTabActive: CSSProperties = {
  ...mobileTab,
  color: 'var(--color-accent)',
  background: 'var(--color-selected)',
  borderBottomColor: 'var(--color-accent)',
}

interface CockpitProps {
  onBack?: () => void
  isMobile?: boolean
}

type CockpitView = 'single' | 'inspector'

export function BuilderCockpit({ onBack, isMobile = false }: CockpitProps) {
  const query = useGatewayRuntimeManifest()
  const fact = query.data?.execution.builder
  const snapshot = fact?.value
  const isLoading = query.isLoading
  const error = query.error instanceof Error ? query.error.message : null

  const [selection, setSelection] = useState<{ initiativeId: string; packetId: string } | null>(null)
  const [view, setView] = useState<CockpitView>('single')
  const [mobileView, setMobileView] = useState<'tree' | 'worker' | 'inspector'>('tree')

  const selectedPacket = useMemo<BuilderPacketStatus | null>(() => {
    if (!snapshot || !selection) return null
    for (const initiative of snapshot.initiatives) {
      if (initiative.initiative_id !== selection.initiativeId) continue
      return initiative.packets.find(p => p.packet_id === selection.packetId) ?? null
    }
    return null
  }, [snapshot, selection])

  const activeCount = useMemo(() => {
    if (!snapshot) return 0
    return snapshot.initiatives.flatMap(i => i.packets)
      .filter(p => p.run?.state === 'running').length
  }, [snapshot])

  const attentionCount = useMemo(() => {
    if (!snapshot) return 0
    return snapshot.initiatives.flatMap(i => i.packets)
      .filter(p => p.task_state === 'blocked' || p.task_state === 'failed' || p.blocked_reason).length
  }, [snapshot])

  // Loading state
  if (isLoading && !snapshot) {
    return (
      <div style={{ ...cockpitRoot, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
        <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>Loading Builder state…</p>
      </div>
    )
  }

  // Error state
  if (error && !snapshot) {
    return (
      <div style={{ ...cockpitRoot, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, flexDirection: 'column', gap: 8 }}>
        <p style={{ fontSize: 13, color: '#F44336', fontWeight: 600 }}>Builder unavailable</p>
        <p style={{ fontSize: 11, color: 'var(--ink-2)' }}>{error}</p>
      </div>
    )
  }

  if (!snapshot) {
    return (
      <div style={{ ...cockpitRoot, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
        <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>No Builder data available.</p>
      </div>
    )
  }

  const gridStyle = view === 'inspector' ? withInspector : cockpitRoot

  return (
    <>
      {/* Desktop */}
      {!isMobile && (
      <div style={gridStyle} className="builder-desktop">
        {/* Left: Packet Tree */}
        <div style={panelBase}>
          {onBack && (
            <button
              onClick={onBack}
              style={{
                minHeight: 44,
                background: 'none',
                border: 'none',
                padding: '8px 12px',
                cursor: 'pointer',
                color: 'var(--color-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontFamily: 'var(--font-body)',
                fontSize: 13,
              }}
            >
              <ArrowLeft size={12} /> back
            </button>
          )}
          <div style={toolbarStyle}>
            <span>Packets</span>
            <span style={{ marginLeft: 'auto', color: 'var(--ink-3)' }}>
              {activeCount} active / {attentionCount} attention
            </span>
          </div>
          <BuilderPacketTree
            snapshot={snapshot}
            selected={selection}
            onSelect={(iId, pId) => setSelection({ initiativeId: iId, packetId: pId })}
          />
        </div>

        {/* Center: Worker Pane / Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={toolbarStyle}>
            <button
              style={view === 'single' ? activeTab : toolbarButton}
              onClick={() => setView('single')}
            >
              <List size={12} /> single
            </button>
            <button
              style={view === 'inspector' ? activeTab : toolbarButton}
              onClick={() => setView('inspector')}
            >
              <Grid size={12} /> inspector
            </button>
            <span style={{ marginLeft: 'auto', fontSize: 9 }}>
              {selection ? `${selection.packetId.slice(0, 8)}…` : 'no selection'}
            </span>
          </div>
          <OperatorControls snapshot={snapshot} selectedPacket={selectedPacket} />
          <div style={{ flex: 1, minHeight: 0 }}>
            <WorkerPane packet={selectedPacket} />
          </div>
        </div>

        {/* Right: Inspector (when enabled) */}
        {view === 'inspector' && (
          <div style={{ ...panelBase, borderRight: 'none', borderLeft: '1px solid var(--color-separator)', display: 'flex', flexDirection: 'column' }}>
            <OperatorControls snapshot={snapshot} selectedPacket={selectedPacket} />
            <WorkerInspector packet={selectedPacket} />
          </div>
        )}
      </div>
      )}

      {/* Mobile */}
      {isMobile && (
      <div style={mobileRoot} className="builder-mobile">
        <div style={mobileSurfaceHeader}>
          {onBack && (
            <button type="button" onClick={onBack} style={mobileBackButton}>
              <ArrowLeft size={16} /> Back to Work
            </button>
          )}
          <h1 style={mobileTitleStyle}>Builder details</h1>
          <span style={mobileStatusStyle}>{activeCount} active · {attentionCount} attention</span>
        </div>
        <div style={mobileTabBar}>
          <button
            style={mobileView === 'tree' ? mobileTabActive : mobileTab}
            onClick={() => setMobileView('tree')}
          >
            packets
          </button>
          <button
            style={mobileView === 'worker' ? mobileTabActive : mobileTab}
            onClick={() => setMobileView('worker')}
          >
            worker
          </button>
          <button
            style={mobileView === 'inspector' ? mobileTabActive : mobileTab}
            onClick={() => setMobileView('inspector')}
          >
            inspector
          </button>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {mobileView === 'tree' && (
            <BuilderPacketTree
              snapshot={snapshot}
              selected={selection}
              onSelect={(iId, pId) => {
                setSelection({ initiativeId: iId, packetId: pId })
                setMobileView('worker')
              }}
            />
          )}
          {mobileView === 'worker' && (
            <>
              <OperatorControls snapshot={snapshot} selectedPacket={selectedPacket} />
              <WorkerPane packet={selectedPacket} />
            </>
          )}
          {mobileView === 'inspector' && (
            <WorkerInspector packet={selectedPacket} />
          )}
        </div>
      </div>
      )}
    </>
  )
}
