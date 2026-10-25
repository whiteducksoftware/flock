/**
 * Artifacts flowing from one agent to another in the Flow view: a neutral
 * line labelled `SupportTicket · 8`, `◆ billing · 3` for a decision option,
 * dotted with a hatch swatch for the UNSURE route, and amber, dashed and
 * moving while the target agent works on this type.
 */

import React from 'react';
import { BaseEdge, EdgeProps } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useSettingsStore } from '../../store/settingsStore';
import { shortTypeName } from '../../utils/typeName';
import { EdgeLabel, edgeStyles as styles, useEdgePath, useEdgeWidth } from './edgeParts';

export interface MessageFlowEdgeData {
  messageType: string;
  messageCount: number;
  artifactIds: string[];
  latestTimestamp: string;
  labelOffset?: number; // Vertical offset so labels of parallel edges do not overlap
  decisionChoice?: string; // Decision edges: the option this edge carries
  decisionUnsure?: boolean; // Decision edges: below-threshold (UNSURE) branch
}

const MessageFlowEdge: React.FC<EdgeProps> = (props) => {
  const { id, target, markerEnd, data } = props;
  const edge = data as MessageFlowEdgeData | undefined;
  const [path, labelX, labelY] = useEdgePath(props);
  const width = useEdgeWidth();
  const animate = useSettingsStore((state) => state.graph.edgeAnimation);
  const inFlight = useGraphStore((state) => {
    if (!edge) return false;
    for (const run of state.inFlight.values()) {
      if (run.agent === target && run.types.includes(edge.messageType)) return true;
    }
    return false;
  });

  const decision = edge?.decisionChoice !== undefined;
  const unsure = Boolean(edge?.decisionUnsure);
  const count = edge?.messageCount ?? 0;
  const classes = [styles.line, unsure && styles.unsure, inFlight && styles.flight, inFlight && animate && styles.moving]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <BaseEdge id={id} path={path} className={classes} style={{ strokeWidth: width }} markerEnd={markerEnd} />
      {edge && (
        <EdgeLabel x={labelX} y={labelY + (edge.labelOffset ?? 0)} dashed={unsure} title={edge.messageType}>
          {unsure ? (
            <>
              <span className={`hatch ${styles.swatch}`} />
              {edge.decisionChoice ?? 'UNSURE'} · {count}
            </>
          ) : decision ? (
            <>
              <span className={styles.diamond}>◆</span>
              {edge.decisionChoice} · {count}
            </>
          ) : (
            <>
              {shortTypeName(edge.messageType)} · {count}
            </>
          )}
        </EdgeLabel>
      )}
    </>
  );
};

export default MessageFlowEdge;
