import React from 'react';
import {
  BaseEdge,
  EdgeProps,
  getBezierPath,
  getStraightPath,
  getSmoothStepPath,
  getSimpleBezierPath,
  EdgeLabelRenderer
} from '@xyflow/react';
import { useSettingsStore } from '../../store/settingsStore';

/**
 * Phase 4: Graph Visualization & Dual Views - MessageFlowEdge Component
 *
 * Custom edge for Agent View showing message flow between agents.
 * Features:
 * - Animated edge to show active message flow
 * - Label with message type and count (e.g., "Movie (3)")
 * - Arrow marker at target
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 */

export interface MessageFlowEdgeData {
  messageType: string;
  messageCount: number;
  artifactIds: string[];
  latestTimestamp: string;
  labelOffset?: number; // Phase 11: Vertical offset to prevent label overlap
}

const MessageFlowEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  style = {},
  markerEnd,
  data,
}) => {
  // Get edge settings from settings store
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const edgeStrokeWidth = useSettingsStore((state) => state.graph.edgeStrokeWidth);
  const edgeAnimation = useSettingsStore((state) => state.graph.edgeAnimation);
  const showEdgeLabels = useSettingsStore((state) => state.graph.showEdgeLabels);

  // Use appropriate path function based on settings
  const getPath = () => {
    const params = { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition };
    switch (edgeType) {
      case 'straight':
        return getStraightPath(params);
      case 'smoothstep':
        return getSmoothStepPath(params);
      case 'simplebezier':
        return getSimpleBezierPath(params);
      case 'bezier':
      default:
        return getBezierPath(params);
    }
  };

  const [edgePath, labelX, labelY] = getPath();

  // Phase 11 Bug Fix: Apply label offset to prevent overlap when multiple edges exist
  const edgeData = data as MessageFlowEdgeData | undefined;
  const labelOffset = edgeData?.labelOffset || 0;

  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: 'var(--color-edge-message)',
          strokeWidth: isHovered ? edgeStrokeWidth + 1 : edgeStrokeWidth,
          animation: edgeAnimation ? 'dash 20s linear infinite' : 'none',
          transition: 'var(--transition-all)',
          filter: isHovered ? 'drop-shadow(0 0 4px var(--color-edge-message))' : 'none',
        }}
        markerEnd={markerEnd}
      />
      {label && showEdgeLabels && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY + labelOffset}px)`,
              fontSize: 'var(--font-size-caption)',
              fontWeight: 'var(--font-weight-medium)',
              background: 'var(--color-edge-label-bg)',
              color: 'var(--color-edge-label-text)',
              padding: 'var(--spacing-1) var(--spacing-2)',
              borderRadius: 'var(--radius-sm)',
              border: 'var(--border-width-1) solid var(--color-edge-message)',
              pointerEvents: 'all',
              backdropFilter: 'blur(var(--blur-sm))',
              boxShadow: 'var(--shadow-sm)',
              transition: 'var(--transition-all)',
            }}
            className="nodrag nopan"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
      <style>{`
        @keyframes dash {
          to {
            stroke-dashoffset: -100;
          }
        }
      `}</style>
    </>
  );
};

export default MessageFlowEdge;
