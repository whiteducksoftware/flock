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
 * Phase 1.5: Logic Operations UX - PendingBatchEdge Component
 *
 * Custom edge for showing artifacts "en route" to BatchSpec accumulation.
 * Visually distinct from normal message_flow edges to indicate batching state.
 *
 * Features:
 * - Orange dashed line (matches BatchSpec theme)
 * - Label with ⊞ symbol + batch progress
 * - Hover tooltip showing batch size/target
 * - Animated dashing to show "accumulating" state
 *
 * Edge type: "pending_batch"
 * Created by backend graph_builder.py when artifacts are accumulating in batches
 */

export interface PendingBatchEdgeData {
  artifactId: string;
  artifactType: string;
  subscriptionIndex: number;
  itemsCollected: number;
  itemsTarget: number | null;
  labelOffset?: number;
}

const PendingBatchEdge: React.FC<EdgeProps> = ({
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

  const edgeData = data as PendingBatchEdgeData | undefined;
  const labelOffset = edgeData?.labelOffset || 0;
  const itemsCollected = edgeData?.itemsCollected || 0;
  const itemsTarget = edgeData?.itemsTarget;

  const [isHovered, setIsHovered] = React.useState(false);

  // Orange color theme for BatchSpec
  const edgeColor = 'var(--color-orange-500, #fb923c)';
  const edgeColorHover = 'var(--color-orange-600, #ea580c)';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: isHovered ? edgeColorHover : edgeColor,
          strokeWidth: isHovered ? edgeStrokeWidth + 1 : edgeStrokeWidth,
          strokeDasharray: '8,6', // Dashed line for "pending" state
          opacity: 0.7,
          transition: 'var(--transition-all)',
          filter: isHovered ? `drop-shadow(0 0 6px ${edgeColor})` : 'none',
          animation: 'pending-dash 2s linear infinite',
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
              fontWeight: 'var(--font-weight-semibold)',
              background: 'rgba(251, 146, 60, 0.12)', // Orange tinted background
              color: 'var(--color-orange-700, #c2410c)',
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              border: `1.5px dashed ${edgeColor}`,
              pointerEvents: 'all',
              backdropFilter: 'blur(var(--blur-sm))',
              boxShadow: isHovered ? 'var(--shadow-md)' : 'var(--shadow-xs)',
              transition: 'var(--transition-all)',
              cursor: 'help',
            }}
            className="nodrag nopan"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            title={`Batch accumulating: ${itemsCollected}${itemsTarget ? `/${itemsTarget}` : ''} items\nArtifact: ${edgeData?.artifactType || 'unknown'}`}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
      <style>{`
        @keyframes pending-dash {
          to {
            stroke-dashoffset: -28;
          }
        }
      `}</style>
    </>
  );
};

export default PendingBatchEdge;
