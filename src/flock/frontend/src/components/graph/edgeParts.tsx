/**
 * What the board's edges share: the path the settings ask for and the label
 * (docs/internal/design-system/README.md, Edges).
 */

import React from 'react';
import {
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
  getSimpleBezierPath,
  getSmoothStepPath,
  getStraightPath,
} from '@xyflow/react';
import { useSettingsStore } from '../../store/settingsStore';
import styles from './edges.module.css';

/** The edge's path and label position, in the shape Settings › Graph chose. */
export const useEdgePath = ({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
}: Pick<EdgeProps, 'sourceX' | 'sourceY' | 'targetX' | 'targetY' | 'sourcePosition' | 'targetPosition'>) => {
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const params = { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition };
  switch (edgeType) {
    case 'straight':
      return getStraightPath(params);
    case 'smoothstep':
      return getSmoothStepPath(params);
    case 'simplebezier':
      return getSimpleBezierPath(params);
    default:
      return getBezierPath(params);
  }
};

/** The stroke width from Settings › Graph. */
export const useEdgeWidth = (): number => useSettingsStore((state) => state.graph.edgeStrokeWidth);

export const EdgeLabel: React.FC<{
  x: number;
  y: number;
  /** Pending or unsure: a dashed border */
  dashed?: boolean;
  title?: string;
  children: React.ReactNode;
}> = ({ x, y, dashed, title, children }) => {
  const show = useSettingsStore((state) => state.graph.showEdgeLabels);
  if (!show) return null;
  return (
    <EdgeLabelRenderer>
      <div
        className={`nodrag nopan mono ${styles.label} ${dashed ? styles.dashed : ''}`}
        style={{ transform: `translate(-50%, -50%) translate(${x}px, ${y}px)` }}
        title={title}
      >
        {children}
      </div>
    </EdgeLabelRenderer>
  );
};

export { styles as edgeStyles };
