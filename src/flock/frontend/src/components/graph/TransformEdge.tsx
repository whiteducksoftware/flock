/**
 * An agent turning one artifact into another in the Blackboard view: a
 * neutral line labelled with the agent.
 */

import React from 'react';
import { BaseEdge, EdgeProps } from '@xyflow/react';
import { EdgeLabel, edgeStyles as styles, useEdgePath, useEdgeWidth } from './edgeParts';

export interface TransformEdgeData {
  transformerAgent: string;
  runId: string;
  durationMs?: number;
  labelOffset?: number; // Vertical offset so labels of parallel edges do not overlap
}

const TransformEdge: React.FC<EdgeProps> = (props) => {
  const { id, markerEnd, data } = props;
  const edge = data as TransformEdgeData | undefined;
  const [path, labelX, labelY] = useEdgePath(props);
  const width = useEdgeWidth();

  return (
    <>
      <BaseEdge id={id} path={path} className={styles.line} style={{ strokeWidth: width }} markerEnd={markerEnd} />
      {edge && (
        <EdgeLabel
          x={labelX}
          y={labelY + (edge.labelOffset ?? 0)}
          title={edge.durationMs !== undefined ? `${edge.transformerAgent} · ${Math.round(edge.durationMs)} ms` : undefined}
        >
          {edge.transformerAgent}
        </EdgeLabel>
      )}
    </>
  );
};

export default TransformEdge;
