'use client'
import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: (error: Error, reset: () => void) => ReactNode
  name?: string
}

interface State {
  error: Error | null
}

/** Catches render errors in a subtree so one bad panel can't blank the page. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: unknown) {
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary${this.props.name ? ' ' + this.props.name : ''}]`, error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (error) {
      if (this.props.fallback) return this.props.fallback(error, this.reset)
      return (
        <div style={{
          margin: 16,
          padding: '14px 16px',
          background: 'var(--bg)',
          border: '1px solid var(--c-red)',
          borderRadius: 4,
          color: 'var(--ink-2)',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
        }}>
          <div style={{ color: 'var(--c-red)', fontWeight: 700, marginBottom: 6 }}>
            Something crashed{this.props.name ? ` in ${this.props.name}` : ''}
          </div>
          <div style={{ marginBottom: 10 }}>{error.message}</div>
          <button
            onClick={this.reset}
            style={{
              padding: '4px 10px',
              background: 'var(--surface)',
              border: '1px solid var(--line)',
              borderRadius: 4,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--ink)',
              cursor: 'pointer',
            }}
          >
            retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
