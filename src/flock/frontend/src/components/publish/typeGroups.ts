/**
 * The composer's type list: "Your types", "Decisions" and "System types",
 * each in the order the server lists them.
 */

import type { ArtifactType } from '../../services/api';
import { shortTypeName } from '../../utils/typeName';

/** Types Flock itself publishes: workflow errors, timer ticks, explanations. */
const SYSTEM_PREFIXES = ['flock.models.system_artifacts.', 'flock.decisions.explain.'];

export const isSystemType = (name: string): boolean => SYSTEM_PREFIXES.some((prefix) => name.startsWith(prefix));

/** `Decision[app.Route]`: the decisions of a question; a decision handle subscribes to it. */
export const isDecisionType = (name: string): boolean => name.startsWith('Decision[');

/** `Decision[app.Route]` -> `Route` */
export const questionOf = (decisionType: string): string => shortTypeName(decisionType).slice('Decision['.length, -1);

export const fieldCount = (type: ArtifactType): number => Object.keys(type.schema?.properties ?? {}).length;

export interface TypeGroups {
  yours: ArtifactType[];
  decisions: ArtifactType[];
  system: ArtifactType[];
}

/** The types whose short name contains `query` (any case), by group. */
export function groupTypes(types: ArtifactType[], query = ''): TypeGroups {
  const needle = query.trim().toLowerCase();
  const groups: TypeGroups = { yours: [], decisions: [], system: [] };
  types.forEach((type) => {
    if (!shortTypeName(type.name).toLowerCase().includes(needle)) return;
    if (isSystemType(type.name)) groups.system.push(type);
    else if (isDecisionType(type.name)) groups.decisions.push(type);
    else groups.yours.push(type);
  });
  return groups;
}
