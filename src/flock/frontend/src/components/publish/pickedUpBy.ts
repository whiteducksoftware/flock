/** Which agents an artifact of a type reaches: its subscribers, and theirs. */

import type { Agent } from '../../services/api';
import { isDecisionType } from './typeGroups';

export interface PickedUp {
  /** The agents subscribed to the type */
  direct: Agent[];
  /** The agents subscribed to what the direct ones publish */
  onward: Agent[];
  /** True if a decision leads there: which onward agents run depends on it */
  viaDecisions: boolean;
}

export function pickedUpBy(typeName: string, agents: Agent[]): PickedUp {
  const direct = agents.filter((agent) => (agent.subscriptions ?? []).includes(typeName));
  const outputs = new Set(direct.flatMap((agent) => agent.output_types ?? []));
  const reached = (agent: Agent) => (agent.subscriptions ?? []).filter((type) => outputs.has(type));
  const onward = agents.filter((agent) => !direct.includes(agent) && reached(agent).length > 0);
  const viaDecisions = onward.some((agent) => reached(agent).some(isDecisionType));
  return { direct, onward, viaDecisions };
}

/** `a`, `a or b`, `a, b or c` */
export function orList(names: string[]): string {
  if (names.length < 2) return names.join('');
  return `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}`;
}
