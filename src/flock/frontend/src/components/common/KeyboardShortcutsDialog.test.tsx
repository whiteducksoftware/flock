import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import KeyboardShortcutsDialog from './KeyboardShortcutsDialog';

describe('KeyboardShortcutsDialog', () => {
  it('is a modal dialog with the keys of the board, the panels, the composer and the palette', () => {
    render(<KeyboardShortcutsDialog isOpen onClose={() => {}} />);

    const dialog = screen.getByRole('dialog', { name: 'Keyboard shortcuts' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    // Every group is named by its heading
    for (const name of ['Board', 'Panels', 'Publish composer', 'Palette']) {
      expect(within(dialog).getByRole('region', { name })).toBeInTheDocument();
    }
    expect(within(dialog).getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual([
      'Board',
      'Panels',
      'Publish composer',
      'Palette',
    ]);
    const text = dialog.textContent ?? '';
    for (const description of [
      'Search agents, types and runs, or run a command',
      'Unfold or fold the selected node',
      'Put the selected node in focus',
      'Leave focus, close a panel, else fold',
      'Publish',
      'Run the second action of a result',
    ]) {
      expect(text).toContain(description);
    }
    // Space, Enter and Esc as keys
    expect(within(dialog).getAllByText('Space').length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText('Enter').length).toBeGreaterThan(0);
  });

  it('takes the focus, keeps Tab inside, and closes with Esc or Ctrl+/ giving the focus back', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const onClose = vi.fn();
    const { rerender } = render(<KeyboardShortcutsDialog isOpen onClose={onClose} />);

    const close = screen.getByRole('button', { name: 'Close keyboard shortcuts' });
    expect(close).toHaveFocus();
    // The close button is the only stop: Tab stays on it
    fireEvent.keyDown(close, { key: 'Tab' });
    expect(close).toHaveFocus();

    fireEvent.keyDown(close, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(close, { key: '/', ctrlKey: true });
    expect(onClose).toHaveBeenCalledTimes(2);

    rerender(<KeyboardShortcutsDialog isOpen={false} onClose={onClose} />);
    expect(opener).toHaveFocus();
    opener.remove();
  });
});
