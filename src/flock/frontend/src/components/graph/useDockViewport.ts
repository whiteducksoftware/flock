import { useEffect, useRef } from 'react';
import { useNodesInitialized, useReactFlow, useStore, type Viewport } from '@xyflow/react';
import { motionMs } from './animatePositions';

/**
 * The expanded timeline dock leaves the board a strip, which may show none
 * of the graph: fit the graph into it, and give the view back on collapse.
 * The fit waits until React Flow has the board's new height and the graph is
 * measured; earlier, it would center the graph on the old height, or wait
 * inside React Flow and land after a collapse.
 */
export function useDockViewport(dockOpen: boolean): void {
  const { fitView, getViewport, setViewport } = useReactFlow();
  const height = useStore((state) => state.height);
  const measured = useNodesInitialized();
  const saved = useRef<Viewport | null>(null);
  // The board's height when the dock opened, until the fit is done
  const due = useRef<number | null>(null);

  useEffect(() => {
    if (dockOpen) {
      saved.current = getViewport();
      due.current = height;
      return;
    }
    due.current = null;
    if (saved.current) {
      setViewport(saved.current, { duration: motionMs(200) });
      saved.current = null;
    }
    // Only the dock's state starts or ends this; the flow's functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dockOpen]);

  useEffect(() => {
    if (!dockOpen || due.current === null || !measured || height === due.current) return;
    due.current = null;
    fitView({ duration: motionMs(200) });
  }, [dockOpen, height, measured, fitView]);
}
