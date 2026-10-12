import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, useStoreApi } from '@xyflow/react';
import { useLayoutEffect } from 'react';
import CanvasDock from './CanvasDock';
import { glideNodes } from './glideNodes';
import { useGraphStore } from '../../store/graphStore';

const view = { zoomIn: vi.fn(), zoomOut: vi.fn(), fitView: vi.fn() };
vi.mock('@xyflow/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@xyflow/react')>();
  return { ...actual, useReactFlow: () => ({ ...actual.useReactFlow, ...view }) };
});

const AtZoom = ({ zoom, children }: { zoom: number; children: React.ReactNode }) => {
  const store = useStoreApi();
  useLayoutEffect(() => {
    store.setState({ transform: [0, 0, zoom] });
  }, [store, zoom]);
  return <>{children}</>;
};

const renderDock = (props: Partial<React.ComponentProps<typeof CanvasDock>> = {}) => {
  const onLayout = vi.fn();
  const onAutoArrange = vi.fn();
  render(
    <ReactFlowProvider>
      <AtZoom zoom={0.75}>
        <CanvasDock layout="hierarchical-horizontal" autoArrange onLayout={onLayout} onAutoArrange={onAutoArrange} {...props} />
      </AtZoom>
    </ReactFlowProvider>,
  );
  return { onLayout, onAutoArrange };
};

describe('CanvasDock', () => {
  afterEach(() => vi.clearAllMocks());

  it('fits the board where a glide takes the nodes, not on their way (#650)', () => {
    vi.useFakeTimers();
    try {
      useGraphStore.setState({ nodes: [{ id: 'a', type: 'agent', position: { x: 0, y: 0 }, data: {} }] });
      renderDock();
      glideNodes(new Map([['a', { x: 900, y: 0 }]]));
      fireEvent.click(screen.getByRole('button', { name: 'Fit to screen' }));
      expect(view.fitView).not.toHaveBeenCalled();

      act(() => void vi.advanceTimersByTime(300));
      expect(view.fitView).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
      useGraphStore.setState(useGraphStore.getInitialState(), true);
    }
  });

  it('zooms, says the zoom level and fits the board', () => {
    renderDock();
    const dock = screen.getByRole('toolbar', { name: 'Canvas' });

    expect(dock.textContent).toContain('75%');
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fit to screen' }));

    expect(view.zoomIn).toHaveBeenCalledOnce();
    expect(view.zoomOut).toHaveBeenCalledOnce();
    expect(view.fitView).toHaveBeenCalledOnce();
  });

  it('lays the board out in each mode from its menu', () => {
    const { onLayout } = renderDock();
    const button = screen.getByRole('button', { name: /Layout: Hierarchical/ });

    fireEvent.click(button);
    const items = screen.getAllByRole('menuitemradio');
    expect(items.map((item) => item.textContent)).toEqual([
      'Hierarchical, left to right',
      'Hierarchical, top down',
      'Circular',
      'Grid',
      'Random',
    ]);
    expect(items[0]!.getAttribute('aria-checked')).toBe('true');

    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Grid' }));
    expect(onLayout).toHaveBeenCalledWith('grid');
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('moves through the menu with the arrow keys and closes it with Esc, which goes no further', () => {
    renderDock();
    fireEvent.click(screen.getByRole('button', { name: /Layout/ }));
    const menu = screen.getByRole('menu');
    expect(document.activeElement).toBe(screen.getByRole('menuitemradio', { name: 'Hierarchical, left to right' }));

    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(screen.getByRole('menuitemradio', { name: 'Hierarchical, top down' }));
    fireEvent.keyDown(menu, { key: 'ArrowUp' });
    fireEvent.keyDown(menu, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(screen.getByRole('menuitemradio', { name: 'Random' }));

    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    act(() => {
      menu.dispatchEvent(escape);
    });
    expect(escape.defaultPrevented).toBe(true);
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /Layout/ }));
  });

  it('closes the menu when the keyboard focus leaves it, so its Esc reaches no menu', () => {
    renderDock();
    fireEvent.click(screen.getByRole('button', { name: /Layout/ }));
    expect(screen.getByRole('menu')).toBeTruthy();

    // Tab moves on to Auto-arrange
    const next = screen.getByRole('switch', { name: 'Auto-arrange' });
    act(() => next.focus());
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(next);
  });

  it('closes the menu with Shift+Tab back to its button, and with a click on that button', () => {
    renderDock();
    const button = screen.getByRole('button', { name: /Layout/ });

    fireEvent.click(button);
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Tab', shiftKey: true });
    expect(screen.queryByRole('menu')).toBeNull();

    // A click takes the focus to the button first, then toggles it
    fireEvent.click(button);
    act(() => button.focus());
    fireEvent.click(button);
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('switches auto-arrange', () => {
    const { onAutoArrange } = renderDock({ autoArrange: false });
    const toggle = screen.getByRole('switch', { name: 'Auto-arrange' });

    expect(toggle.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(toggle);
    expect(onAutoArrange).toHaveBeenCalledWith(true);
  });
});
