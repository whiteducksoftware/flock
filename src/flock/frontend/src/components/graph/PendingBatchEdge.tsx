/**
 * An artifact waiting in a batch: dashed in the quiet text color, labelled
 * with the batch's progress.
 */

import React from 'react';
import { BaseEdge, EdgeProps } from '@xyflow/react';
import { EdgeLabel, edgeStyles as styles, useEdgePath, useEdgeWidth } from './edgeParts';

export interface PendingBatchEdgeData {
  artifactId: string;
  artifactType: string;
  subscriptionIndex: number;
  itemsCollected: number;
  itemsTarget: number | null;
  labelOffset?: number;
}

const PendingBatchEdge: React.FC<EdgeProps> = (props) => {
  const { id, markerEnd, data } = props;
  const edge = data as PendingBatchEdgeData | undefined;
  const [path, labelX, labelY] = useEdgePath(props);
  const width = useEdgeWidth();

  return (
    <>
      <BaseEdge id={id} path={path} className={`${styles.line} ${styles.pending}`} style={{ strokeWidth: width }} markerEnd={markerEnd} />
      {edge && (
        <EdgeLabel x={labelX} y={labelY + (edge.labelOffset ?? 0)} dashed>
          batch {edge.itemsCollected} / {edge.itemsTarget ?? '∞'}
        </EdgeLabel>
      )}
    </>
  );
};

export default PendingBatchEdge;
