import { useEffect, useRef } from 'react';
import { useReactFlow, type Viewport } from '@xyflow/react';
import { motionMs } from './animatePositions';

/**
 * The expanded timeline dock leaves the board a strip, which may show none
 * of the graph: fit the graph into it, and give the view back on collapse.
 */
export function useDockViewport(dockOpen: boolean): void {
  const { fitView, getViewport, setViewport } = useReactFlow();
  const before = useRef<Viewport | null>(null);

  useEffect(() => {
    if (dockOpen) {
      before.current = getViewport();
      // Once the board has its new height
      const timer = window.setTimeout(() => fitView({ duration: motionMs(200) }), 0);
      return () => window.clearTimeout(timer);
    }
    if (before.current) {
      setViewport(before.current, { duration: motionMs(200) });
      before.current = null;
    }
    // The flow's functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dockOpen]);
}
