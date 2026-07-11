'use client'

import { useCallback, useRef, useState } from 'react'
import { uploadCaptureFile } from '@/lib/gateway'

export function CapturePanel() {
  const [status, setStatus] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (file: File) => {
    setStatus('Uploading...')
    const result = await uploadCaptureFile(file)
    if (result) {
      setStatus(`${result.status}: ${result.message}`)
    } else {
      setStatus('upload failed')
    }
  }, [])

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragActive(false)
      const file = e.dataTransfer.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const onDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
  }, [])

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      role="button"
      tabIndex={0}
      style={{
        border: `1px dashed ${dragActive ? 'var(--c-green)' : 'var(--line)'}`,
        borderRadius: 4,
        padding: 16,
        cursor: 'pointer',
        background: dragActive ? 'var(--bg)' : 'transparent',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.webp,.gif"
        onChange={onChange}
        onClick={e => e.stopPropagation()}
        style={{ display: 'none' }}
      />
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-2)' }}>
        DROP FILE OR CLICK TO CAPTURE
      </div>
      {status && (
        <div
          style={{
            marginTop: 8,
            fontFamily: 'var(--font-body)',
            fontSize: 12,
            color: 'var(--ink)',
          }}
        >
          {status}
        </div>
      )}
    </div>
  )
}
