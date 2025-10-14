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
 * Phase 1.5: Logic Operations UX - PendingJoinEdge Component
 *
 * Custom edge for showing artifacts "en route" to JoinSpec correlation groups.
 * Visually distinct from normal message_flow edges to indicate waiting state.
 *
 * Features:
 * - Purple dashed line (matches JoinSpec theme)
 * - Label with ⋈ symbol + correlation key
 * - Hover tooltip showing waiting_for types
 * - Animated dashing to show "pending" state
 *
 * Edge type: "pending_join"
 * Created by backend graph_builder.py when artifacts are waiting in correlation groups
 */

export interface PendingJoinEdgeData {
  artifactId: string;
  artifactType: string;
  correlationKey: string;
  subscriptionIndex: number;
  waitingFor: string[];
  labelOffset?: number;
}

const PendingJoinEdge: React.FC<EdgeProps> = ({
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

  const edgeData = data as PendingJoinEdgeData | undefined;
  const labelOffset = edgeData?.labelOffset || 0;
  const waitingFor = edgeData?.waitingFor || [];

  const [isHovered, setIsHovered] = React.useState(false);

  // Purple color theme for JoinSpec
  const edgeColor = 'var(--color-purple-500, #a855f7)';
  const edgeColorHover = 'var(--color-purple-600, #9333ea)';

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
              background: 'rgba(168, 85, 247, 0.12)', // Purple tinted background
              color: 'var(--color-purple-700, #7e22ce)',
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
            title={
              waitingFor.length > 0
                ? `Waiting for: ${waitingFor.join(', ')}\nArtifact: ${edgeData?.artifactType || 'unknown'}`
                : `Correlation pending\nArtifact: ${edgeData?.artifactType || 'unknown'}`
            }
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

export default PendingJoinEdge;
