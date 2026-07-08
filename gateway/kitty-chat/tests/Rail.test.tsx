import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Rail } from '../src/components/Rail';

describe('Rail component snapshots', () => {
  it('matches desktop snapshot', () => {
    const { container } = render(<Rail isMobile={false} activeView="home" theme="day" />);
    expect(container).toMatchSnapshot();
  });

  it('matches mobile bottom tab bar snapshot', () => {
    const { container } = render(<Rail isMobile={true} activeView="home" theme="day" />);
    expect(container).toMatchSnapshot();
  });
});
