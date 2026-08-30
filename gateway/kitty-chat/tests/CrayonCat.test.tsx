import { render, cleanup } from '@testing-library/react';
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest';
import { CatCorner, StateBadge } from '../src/components/CrayonCat';

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
})

describe('CrayonCat responsive mascot', () => {
  afterEach(cleanup);

  it('CatCorner renders with the decorative corner class', () => {
    const { container } = render(<CatCorner state="idle" />);
    const corner = container.querySelector('.cat-corner');
    expect(corner).toBeInTheDocument();
  });

  it('CatCorner is hidden from accessibility tree and non-interactive', () => {
    const { container } = render(<CatCorner state="idle" />);
    const corner = container.querySelector('.cat-corner');
    expect(corner).toHaveAttribute('aria-hidden', 'true');
    expect(corner).toHaveStyle({ pointerEvents: 'none' });
  });

  it('CatCorner includes a child CatBody svg', () => {
    const { container } = render(<CatCorner state="working" />);
    const corner = container.querySelector('.cat-corner');
    expect(corner?.querySelector('svg')).toBeInTheDocument();
    expect(corner?.querySelector('.cat-working')).toBeInTheDocument();
  });
});


describe('Kitty state badge shell treatment', () => {
  afterEach(cleanup);

  it('uses semantic shell typography and separators', () => {
    const { getByText } = render(<StateBadge state="idle" />);
    const style = getByText('idle').getAttribute('style') ?? '';
    expect(style).toContain('font-family: var(--font-body)');
    expect(style).toContain('color: var(--color-text-secondary)');
    expect(style).toContain('border: 1px solid var(--color-separator)');
  });

  // Product acceptance, PR #675: this badge reports the last chat turn, but it
  // sits beside the gateway-connection badge, so a bare "issue" read as a
  // verdict on all of Kitty. It must name what it is about.
  it('says the failure is about the reply, not about Kitty as a whole', () => {
    const { getByText, getByLabelText } = render(<StateBadge state="broke" />);
    expect(getByText('reply failed')).toBeInTheDocument();
    expect(getByLabelText("Kitty's last reply failed")).toBeInTheDocument();
  });

  it('gives every state an accessible description', () => {
    for (const [state, name] of [
      ['idle', 'Kitty is idle'],
      ['working', 'Kitty is working'],
      ['done', 'Kitty finished its reply'],
    ] as const) {
      const { getByLabelText, unmount } = render(<StateBadge state={state} />);
      expect(getByLabelText(name)).toBeInTheDocument();
      unmount();
    }
  });
});
