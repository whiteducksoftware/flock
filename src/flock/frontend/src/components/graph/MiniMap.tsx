import React from 'react';
import { MiniMap as ReactFlowMiniMap, Node } from '@xyflow/react';
import styles from './MiniMap.module.css';

/** The board in small, top right; running agents amber, failed ones coral. */
const nodeClass = (node: Node): string => {
  const status = (node.data as { status?: string } | undefined)?.status;
  if (status === 'running') return styles.running!;
  if (status === 'error') return styles.failed!;
  return styles.node!;
};

const MiniMap: React.FC = () => (
  <ReactFlowMiniMap
    className={styles.minimap}
    nodeClassName={nodeClass}
    nodeBorderRadius={3}
    position="top-right"
    pannable
    zoomable
  />
);

export default MiniMap;
