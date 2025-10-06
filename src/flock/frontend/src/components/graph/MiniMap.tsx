import React from 'react';
import { MiniMap as ReactFlowMiniMap } from '@xyflow/react';

/**
 * Phase 4: Graph Visualization & Dual Views - MiniMap Component
 *
 * Wrapper around React Flow's MiniMap component for graph navigation.
 * Features:
 * - Positioned in bottom-right corner
 * - Size: 150x100px
 * - Color-coded nodes: agents (blue), messages (green)
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 */

const MiniMap: React.FC = () => {
  // Color function for nodes in minimap - using design system colors
  const nodeColor = (node: any) => {
    switch (node.type) {
      case 'agent':
        return '#3b82f6'; // Blue for agents (var(--color-node-agent-border))
      case 'message':
        return '#f59e0b'; // Amber for messages (var(--color-node-message-border))
      default:
        return '#64748b'; // Gray for other nodes (var(--color-idle))
    }
  };

  return (
    <ReactFlowMiniMap
      nodeColor={nodeColor}
      style={{
        width: 150,
        height: 100,
        backgroundColor: 'var(--color-bg-surface)',
        border: 'var(--border-default)',
        borderRadius: 'var(--radius-lg)',
      }}
      maskColor="rgba(10, 10, 11, 0.7)"
      position="bottom-right"
      pannable
      zoomable
    />
  );
};

export default MiniMap;
