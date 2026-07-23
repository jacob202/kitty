import { render, cleanup } from '@testing-library/react';
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest';
import { CatCorner } from '../src/components/CrayonCat';

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
