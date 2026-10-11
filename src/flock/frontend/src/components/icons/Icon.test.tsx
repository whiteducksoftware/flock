import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FlockMark, Icon, ICON_NAMES } from './Icon';

describe('Icon', () => {
  it('draws every icon on the 24 px grid with the theme color', () => {
    for (const name of ICON_NAMES) {
      const { container, unmount } = render(<Icon name={name} />);
      const svg = container.querySelector('svg')!;
      expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(svg.getAttribute('stroke')).toBe('currentColor');
      expect(svg.getAttribute('stroke-width')).toBe('1.8');
      expect(svg.children.length).toBeGreaterThan(0);
      unmount();
    }
  });

  it('is decorative without a label and named with one', () => {
    const { container } = render(<Icon name="search" />);
    expect(container.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');

    render(<Icon name="close" label="Close" size={18} />);
    const named = screen.getByRole('img', { name: 'Close' });
    expect(named.getAttribute('width')).toBe('18');
  });

  it('draws the flock mark with an amber lead chevron', () => {
    const { container } = render(<FlockMark />);
    const strokes = [...container.querySelectorAll('path')].map((p) => p.getAttribute('stroke'));
    expect(strokes).toEqual(['currentColor', 'currentColor', 'var(--signal)']);
  });
});
