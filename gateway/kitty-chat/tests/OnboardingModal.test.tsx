import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { OnboardingModal } from '../src/components/OnboardingModal'

describe('OnboardingModal', () => {
  it('collects a name and theme, then persists first-run completion', () => {
    const values = new Map<string, string>()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
      },
    })
    const onComplete = vi.fn()
    render(<OnboardingModal onComplete={onComplete} />)

    fireEvent.click(screen.getByRole('button', { name: 'continue' }))
    fireEvent.change(screen.getByLabelText('what should kitty call you?'), { target: { value: 'Jacob' } })
    fireEvent.click(screen.getByRole('button', { name: 'night theme' }))
    fireEvent.click(screen.getByRole('button', { name: 'continue' }))
    fireEvent.click(screen.getByRole('button', { name: 'finish setup' }))

    expect(onComplete).toHaveBeenCalledWith({ name: 'Jacob', theme: 'night' })
    expect(window.localStorage.getItem('kitty-onboarded')).toBe('true')
    expect(window.localStorage.getItem('kitty-preferred-name')).toBe('Jacob')
    expect(window.localStorage.getItem('kitty-theme')).toBe('night')
  })
})
