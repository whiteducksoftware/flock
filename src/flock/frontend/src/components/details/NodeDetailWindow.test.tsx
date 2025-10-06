/**
 * Unit tests for NodeDetailWindow component.
 *
 * Tests verify window opening, dragging, resizing, closing, multiple window support,
 * and state persistence for detail windows.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useUIStore } from '../../store/uiStore';

// Mock component - will be replaced by actual implementation
const MockNodeDetailWindow = ({ nodeId }: { nodeId: string }) => {
  const window = useUIStore((state) => state.detailWindows.get(nodeId));
  const updateDetailWindow = useUIStore((state) => state.updateDetailWindow);
  const closeDetailWindow = useUIStore((state) => state.closeDetailWindow);

  if (!window) return null;

  const handleDragStart = (e: React.MouseEvent) => {
    const startX = e.clientX - window.position.x;
    const startY = e.clientY - window.position.y;

    const handleDrag = (moveEvent: MouseEvent) => {
      updateDetailWindow(nodeId, {
        position: {
          x: moveEvent.clientX - startX,
          y: moveEvent.clientY - startY,
        },
      });
    };

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag);
      document.removeEventListener('mouseup', handleDragEnd);
    };

    document.addEventListener('mousemove', handleDrag);
    document.addEventListener('mouseup', handleDragEnd);
  };

  const handleResize = (e: React.MouseEvent) => {
    e.stopPropagation();
    const startWidth = window.size.width;
    const startHeight = window.size.height;
    const startX = e.clientX;
    const startY = e.clientY;

    const handleResizeMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;

      updateDetailWindow(nodeId, {
        size: {
          width: Math.max(400, startWidth + deltaX),
          height: Math.max(300, startHeight + deltaY),
        },
      });
    };

    const handleResizeEnd = () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
    };

    document.addEventListener('mousemove', handleResizeMove);
    document.addEventListener('mouseup', handleResizeEnd);
  };

  return (
    <div
      data-testid={`detail-window-${nodeId}`}
      style={{
        position: 'absolute',
        left: window.position.x,
        top: window.position.y,
        width: window.size.width,
        height: window.size.height,
      }}
    >
      <div
        data-testid={`window-header-${nodeId}`}
        onMouseDown={handleDragStart}
        style={{ cursor: 'move', padding: '8px', background: '#333' }}
      >
        <span>Node: {nodeId}</span>
        <button
          data-testid={`close-button-${nodeId}`}
          onClick={() => closeDetailWindow(nodeId)}
        >
          Close
        </button>
      </div>
      <div data-testid={`window-content-${nodeId}`}>Content</div>
      <div
        data-testid={`resize-handle-${nodeId}`}
        onMouseDown={handleResize}
        style={{
          position: 'absolute',
          bottom: 0,
          right: 0,
          width: '10px',
          height: '10px',
          cursor: 'nwse-resize',
        }}
      />
    </div>
  );
};

describe('NodeDetailWindow', () => {
  beforeEach(() => {
    // Reset UI store before each test
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
      defaultTab: 'liveOutput',
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
    });
  });

  afterEach(() => {
    // Clean up any open windows
    useUIStore.setState({ detailWindows: new Map() });
  });

  describe('Window Opening', () => {
    it('should open window when openDetailWindow is called', () => {
      const { rerender } = render(<MockNodeDetailWindow nodeId="agent-1" />);

      // Window should not exist initially
      expect(screen.queryByTestId('detail-window-agent-1')).not.toBeInTheDocument();

      // Open window
      useUIStore.getState().openDetailWindow('agent-1');
      rerender(<MockNodeDetailWindow nodeId="agent-1" />);

      // Window should now be visible
      expect(screen.getByTestId('detail-window-agent-1')).toBeInTheDocument();
      expect(screen.getByText('Node: agent-1')).toBeInTheDocument();
    });

    it('should open window with default position and size', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const window = useUIStore.getState().detailWindows.get('agent-1');
      expect(window).toBeDefined();
      expect(window?.position).toEqual({ x: 100, y: 100 });
      expect(window?.size).toEqual({ width: 600, height: 400 });
    });

    it('should open window with staggered position for multiple windows', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      useUIStore.getState().openDetailWindow('agent-2');
      useUIStore.getState().openDetailWindow('agent-3');

      const window1 = useUIStore.getState().detailWindows.get('agent-1');
      const window2 = useUIStore.getState().detailWindows.get('agent-2');
      const window3 = useUIStore.getState().detailWindows.get('agent-3');

      expect(window1?.position).toEqual({ x: 100, y: 100 });
      expect(window2?.position).toEqual({ x: 120, y: 120 });
      expect(window3?.position).toEqual({ x: 140, y: 140 });
    });

    it('should use defaultTab preference when opening window', () => {
      useUIStore.setState({ defaultTab: 'messageHistory' });
      useUIStore.getState().openDetailWindow('agent-1');

      const window = useUIStore.getState().detailWindows.get('agent-1');
      expect(window?.activeTab).toBe('messageHistory');
    });

    it('should not create duplicate window if already open', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      const window1 = useUIStore.getState().detailWindows.get('agent-1');

      useUIStore.getState().openDetailWindow('agent-1');
      const window2 = useUIStore.getState().detailWindows.get('agent-1');

      expect(window1).toBe(window2);
      expect(useUIStore.getState().detailWindows.size).toBe(1);
    });
  });

  describe('Window Dragging', () => {
    it('should update window position when dragged', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const header = screen.getByTestId('window-header-agent-1');
      const initialWindow = useUIStore.getState().detailWindows.get('agent-1')!;

      // Simulate drag
      fireEvent.mouseDown(header, { clientX: 150, clientY: 150 });
      fireEvent.mouseMove(document, { clientX: 250, clientY: 250 });
      fireEvent.mouseUp(document);

      const updatedWindow = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(updatedWindow.position.x).toBeGreaterThan(initialWindow.position.x);
      expect(updatedWindow.position.y).toBeGreaterThan(initialWindow.position.y);
    });

    it('should allow dragging window to different positions', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const header = screen.getByTestId('window-header-agent-1');

      // First drag
      fireEvent.mouseDown(header, { clientX: 100, clientY: 100 });
      fireEvent.mouseMove(document, { clientX: 200, clientY: 150 });
      fireEvent.mouseUp(document);

      const position1 = useUIStore.getState().detailWindows.get('agent-1')!.position;

      // Second drag
      fireEvent.mouseDown(header, { clientX: position1.x + 50, clientY: position1.y + 50 });
      fireEvent.mouseMove(document, { clientX: position1.x + 150, clientY: position1.y + 100 });
      fireEvent.mouseUp(document);

      const position2 = useUIStore.getState().detailWindows.get('agent-1')!.position;

      expect(position2.x).toBeGreaterThan(position1.x);
      expect(position2.y).toBeGreaterThan(position1.y);
    });

    it('should have drag cursor on header', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const header = screen.getByTestId('window-header-agent-1');
      expect(header).toHaveStyle({ cursor: 'move' });
    });
  });

  describe('Window Resizing', () => {
    it('should update window size when resized', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const resizeHandle = screen.getByTestId('resize-handle-agent-1');
      const initialWindow = useUIStore.getState().detailWindows.get('agent-1')!;

      // Simulate resize
      fireEvent.mouseDown(resizeHandle, { clientX: 700, clientY: 500 });
      fireEvent.mouseMove(document, { clientX: 800, clientY: 600 });
      fireEvent.mouseUp(document);

      const updatedWindow = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(updatedWindow.size.width).toBeGreaterThan(initialWindow.size.width);
      expect(updatedWindow.size.height).toBeGreaterThan(initialWindow.size.height);
    });

    it('should enforce minimum window size', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const resizeHandle = screen.getByTestId('resize-handle-agent-1');

      // Try to resize smaller than minimum (400x300)
      fireEvent.mouseDown(resizeHandle, { clientX: 700, clientY: 500 });
      fireEvent.mouseMove(document, { clientX: 200, clientY: 200 }); // Very small
      fireEvent.mouseUp(document);

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.size.width).toBeGreaterThanOrEqual(400);
      expect(window.size.height).toBeGreaterThanOrEqual(300);
    });

    it('should have resize cursor on resize handle', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const resizeHandle = screen.getByTestId('resize-handle-agent-1');
      expect(resizeHandle).toHaveStyle({ cursor: 'nwse-resize' });
    });
  });

  describe('Window Closing', () => {
    it('should close window when close button is clicked', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      const { rerender } = render(<MockNodeDetailWindow nodeId="agent-1" />);

      expect(screen.getByTestId('detail-window-agent-1')).toBeInTheDocument();

      // Click close button
      const closeButton = screen.getByTestId('close-button-agent-1');
      fireEvent.click(closeButton);

      rerender(<MockNodeDetailWindow nodeId="agent-1" />);

      expect(screen.queryByTestId('detail-window-agent-1')).not.toBeInTheDocument();
      expect(useUIStore.getState().detailWindows.size).toBe(0);
    });

    it('should remove window from detailWindows map when closed', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      expect(useUIStore.getState().detailWindows.has('agent-1')).toBe(true);

      useUIStore.getState().closeDetailWindow('agent-1');
      expect(useUIStore.getState().detailWindows.has('agent-1')).toBe(false);
    });

    it('should handle closing non-existent window gracefully', () => {
      expect(() => {
        useUIStore.getState().closeDetailWindow('non-existent');
      }).not.toThrow();
    });
  });

  describe('Multiple Windows', () => {
    it('should support multiple windows open simultaneously', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      useUIStore.getState().openDetailWindow('agent-2');
      useUIStore.getState().openDetailWindow('agent-3');

      render(
        <>
          <MockNodeDetailWindow nodeId="agent-1" />
          <MockNodeDetailWindow nodeId="agent-2" />
          <MockNodeDetailWindow nodeId="agent-3" />
        </>
      );

      expect(screen.getByTestId('detail-window-agent-1')).toBeInTheDocument();
      expect(screen.getByTestId('detail-window-agent-2')).toBeInTheDocument();
      expect(screen.getByTestId('detail-window-agent-3')).toBeInTheDocument();
      expect(useUIStore.getState().detailWindows.size).toBe(3);
    });

    it('should maintain independent state for each window', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      useUIStore.getState().openDetailWindow('agent-2');

      const window1 = useUIStore.getState().detailWindows.get('agent-1')!;
      const window2 = useUIStore.getState().detailWindows.get('agent-2')!;

      expect(window1.nodeId).toBe('agent-1');
      expect(window2.nodeId).toBe('agent-2');
      expect(window1.position).not.toEqual(window2.position);
    });

    it('should allow closing one window without affecting others', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      useUIStore.getState().openDetailWindow('agent-2');
      useUIStore.getState().openDetailWindow('agent-3');

      render(
        <>
          <MockNodeDetailWindow nodeId="agent-1" />
          <MockNodeDetailWindow nodeId="agent-2" />
          <MockNodeDetailWindow nodeId="agent-3" />
        </>
      );

      // Close middle window
      fireEvent.click(screen.getByTestId('close-button-agent-2'));

      expect(screen.queryByTestId('detail-window-agent-2')).not.toBeInTheDocument();
      expect(screen.getByTestId('detail-window-agent-1')).toBeInTheDocument();
      expect(screen.getByTestId('detail-window-agent-3')).toBeInTheDocument();
      expect(useUIStore.getState().detailWindows.size).toBe(2);
    });

    it('should key windows by nodeId', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      useUIStore.getState().openDetailWindow('message-123');

      expect(useUIStore.getState().detailWindows.has('agent-1')).toBe(true);
      expect(useUIStore.getState().detailWindows.has('message-123')).toBe(true);
    });
  });

  describe('State Persistence', () => {
    it('should persist window position updates', () => {
      useUIStore.getState().openDetailWindow('agent-1');

      // Update position
      useUIStore.getState().updateDetailWindow('agent-1', {
        position: { x: 300, y: 400 },
      });

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.position).toEqual({ x: 300, y: 400 });
    });

    it('should persist window size updates', () => {
      useUIStore.getState().openDetailWindow('agent-1');

      // Update size
      useUIStore.getState().updateDetailWindow('agent-1', {
        size: { width: 800, height: 600 },
      });

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.size).toEqual({ width: 800, height: 600 });
    });

    it('should persist active tab changes', () => {
      useUIStore.getState().openDetailWindow('agent-1');

      // Change active tab
      useUIStore.getState().updateDetailWindow('agent-1', {
        activeTab: 'messageHistory',
      });

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.activeTab).toBe('messageHistory');
    });

    it('should preserve window state during drag operations', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const header = screen.getByTestId('window-header-agent-1');

      // Perform drag
      fireEvent.mouseDown(header, { clientX: 150, clientY: 150 });
      fireEvent.mouseMove(document, { clientX: 350, clientY: 350 });
      fireEvent.mouseUp(document);

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.nodeId).toBe('agent-1');
      expect(window.size).toEqual({ width: 600, height: 400 }); // Size unchanged
      expect(window.activeTab).toBe('liveOutput'); // Tab unchanged
    });

    it('should preserve window state during resize operations', () => {
      useUIStore.getState().openDetailWindow('agent-1');
      render(<MockNodeDetailWindow nodeId="agent-1" />);

      const resizeHandle = screen.getByTestId('resize-handle-agent-1');

      // Perform resize
      fireEvent.mouseDown(resizeHandle, { clientX: 700, clientY: 500 });
      fireEvent.mouseMove(document, { clientX: 900, clientY: 700 });
      fireEvent.mouseUp(document);

      const window = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(window.nodeId).toBe('agent-1');
      expect(window.position).toEqual({ x: 100, y: 100 }); // Position unchanged
      expect(window.activeTab).toBe('liveOutput'); // Tab unchanged
    });
  });

  describe('Edge Cases', () => {
    it('should handle updateDetailWindow for non-existent window', () => {
      expect(() => {
        useUIStore.getState().updateDetailWindow('non-existent', {
          position: { x: 100, y: 100 },
        });
      }).not.toThrow();

      expect(useUIStore.getState().detailWindows.has('non-existent')).toBe(false);
    });

    it('should handle rapid open/close cycles', () => {
      for (let i = 0; i < 10; i++) {
        useUIStore.getState().openDetailWindow('agent-1');
        expect(useUIStore.getState().detailWindows.has('agent-1')).toBe(true);

        useUIStore.getState().closeDetailWindow('agent-1');
        expect(useUIStore.getState().detailWindows.has('agent-1')).toBe(false);
      }
    });

    it('should handle many simultaneous windows', () => {
      const nodeIds = Array.from({ length: 20 }, (_, i) => `agent-${i}`);

      nodeIds.forEach((nodeId) => {
        useUIStore.getState().openDetailWindow(nodeId);
      });

      expect(useUIStore.getState().detailWindows.size).toBe(20);

      nodeIds.forEach((nodeId) => {
        expect(useUIStore.getState().detailWindows.has(nodeId)).toBe(true);
      });
    });

    it('should handle partial window updates', () => {
      useUIStore.getState().openDetailWindow('agent-1');

      const original = useUIStore.getState().detailWindows.get('agent-1')!;

      // Update only position
      useUIStore.getState().updateDetailWindow('agent-1', {
        position: { x: 500, y: 600 },
      });

      const updated = useUIStore.getState().detailWindows.get('agent-1')!;
      expect(updated.position).toEqual({ x: 500, y: 600 });
      expect(updated.size).toEqual(original.size);
      expect(updated.activeTab).toEqual(original.activeTab);
    });
  });
});
