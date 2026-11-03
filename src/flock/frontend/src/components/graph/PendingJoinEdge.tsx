/**
 * An artifact waiting in a join for its partners: dashed in the quiet text
 * color, labelled with the join key.
 */

import React from 'react';
import { BaseEdge, EdgeProps } from '@xyflow/react';
import { shortTypeName } from '../../utils/typeName';
import { EdgeLabel, edgeStyles as styles, useEdgePath, useEdgeWidth } from './edgeParts';

export interface PendingJoinEdgeData {
  artifactId: string;
  artifactType: string;
  correlationKey: string;
  subscriptionIndex: number;
  waitingFor: string[];
  labelOffset?: number;
}

const PendingJoinEdge: React.FC<EdgeProps> = (props) => {
  const { id, markerEnd, data } = props;
  const edge = data as PendingJoinEdgeData | undefined;
  const [path, labelX, labelY] = useEdgePath(props);
  const width = useEdgeWidth();
  const waiting = edge?.waitingFor.map(shortTypeName).join(', ');

  return (
    <>
      <BaseEdge id={id} path={path} className={`${styles.line} ${styles.pending}`} style={{ strokeWidth: width }} markerEnd={markerEnd} />
      {edge && (
        <EdgeLabel x={labelX} y={labelY + (edge.labelOffset ?? 0)} dashed title={waiting ? `Waiting for ${waiting}` : undefined}>
          ⋈ {edge.correlationKey}
        </EdgeLabel>
      )}
    </>
  );
};

export default PendingJoinEdge;
