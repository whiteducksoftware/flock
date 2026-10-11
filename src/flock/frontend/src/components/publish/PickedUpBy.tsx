/**
 * "Picked up by": the agents subscribed to the type, with what they publish,
 * and one line on the agents that run after them.
 */

import React, { useId } from 'react';
import type { Agent } from '../../services/api';
import { shortTypeName } from '../../utils/typeName';
import { orList, pickedUpBy } from './pickedUpBy';
import { isDecisionType, questionOf } from './typeGroups';
import styles from './PublishComposer.module.css';

const dotClass = (status: string | undefined) =>
  `sdot ${status === 'running' || status === 'active' ? 'run' : status === 'error' ? 'err' : ''}`;

const PickedUpBy: React.FC<{ typeName: string; agents: Agent[] }> = ({ typeName, agents }) => {
  const { direct, onward, viaDecisions } = pickedUpBy(typeName, agents);
  const titleId = useId();
  return (
    <section className={styles.picked} aria-labelledby={titleId}>
      <h3 id={titleId} className={styles.groupLabel}>
        Picked up by
      </h3>
      {direct.length === 0 ? (
        <p className={styles.onward}>No agent subscribes to this type yet.</p>
      ) : (
        <ul className={styles.agents}>
          {direct.map((agent) => (
            <li key={agent.name} className={styles.agent}>
              <span className={dotClass(agent.status)} role="img" aria-label={agent.status || 'idle'} />
              {agent.name}
              {(agent.output_types ?? []).map((output) => (
                <React.Fragment key={output}>
                  {' '}
                  {isDecisionType(output) ? (
                    <span className={`mono ${styles.decision}`} title={output}>
                      <span aria-hidden>◆ </span>
                      {questionOf(output)}
                    </span>
                  ) : (
                    <span className={`mono ${styles.output}`} title={output}>
                      {shortTypeName(output)}
                    </span>
                  )}
                </React.Fragment>
              ))}
            </li>
          ))}
        </ul>
      )}
      {onward.length > 0 && (
        <p className={styles.onward}>
          and from there {orList(onward.map((agent) => agent.name))}, depending on{' '}
          {viaDecisions ? 'the decisions' : 'what they publish'}
        </p>
      )}
    </section>
  );
};

export default PickedUpBy;
