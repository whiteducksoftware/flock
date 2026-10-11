/**
 * What an agent consumes and publishes, with the fields of each type, for
 * the Contract tab of focus mode. Schemas come from `/api/artifact-types`.
 */

import type { Edge, Node } from '@xyflow/react';
import { shortTypeName } from '../../../utils/typeName';

export interface Field {
  name: string;
  /** As Python spells it: `str`, `list[str]`, `int | None` */
  type: string;
  description: string | null;
  required: boolean;
}

export interface ContractEntry {
  type: string;
  label: string;
  decision: boolean;
  note: string | null;
  fields: Field[];
  /** A handle whose decider decides about several types: each subject with its fields */
  subjects?: { type: string; label: string; fields: Field[] }[];
}

export interface Contract {
  consumes: ContractEntry[];
  publishes: ContractEntry[];
}

interface JsonSchema {
  type?: string | string[];
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  $ref?: string;
  enum?: unknown[];
  description?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
}

const PYTHON: Record<string, string> = {
  string: 'str',
  integer: 'int',
  number: 'float',
  boolean: 'bool',
  object: 'dict',
  null: 'None',
};

function typeName(schema: JsonSchema): string {
  if (schema.$ref) return schema.$ref.split('/').pop() ?? 'object';
  if (schema.anyOf) return schema.anyOf.map(typeName).join(' | ');
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(' | ');
  if (Array.isArray(schema.type)) return schema.type.map((type) => PYTHON[type] ?? type).join(' | ');
  if (schema.type === 'array') return `list[${schema.items ? typeName(schema.items) : 'Any'}]`;
  return schema.type ? (PYTHON[schema.type] ?? schema.type) : 'Any';
}

/** The fields of a type's schema, in its order. */
export function fieldsOf(schema: JsonSchema | undefined): Field[] {
  const required = new Set(schema?.required ?? []);
  return Object.entries(schema?.properties ?? {}).map(([name, property]) => ({
    name,
    type: typeName(property),
    description: property.description ?? null,
    required: required.has(name),
  }));
}

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

const dataOf = (node: Node | undefined) =>
  (node?.data ?? {}) as {
    subscriptions?: string[];
    outputTypes?: string[];
    sentByType?: Record<string, number>;
    typeLabels?: Record<string, string>;
  };

/**
 * The agent's contract. A decision handle delivers the subject the decider
 * read, so it shows that subject's fields; a decider's own decisions route to
 * their handles and have no fields of interest.
 */
export function contractOf(
  id: string,
  nodes: Node[],
  schemas: Record<string, JsonSchema>,
  edges: Pick<Edge, 'source' | 'target' | 'data'>[] = [],
): Contract {
  const data = dataOf(nodes.find((node) => node.id === id));
  const labels = data.typeLabels ?? {};

  const consumes = [...new Set(data.subscriptions ?? [])].map((type): ContractEntry => {
    const handle = labels[type]?.startsWith('◆') ? labels[type]!.replace(/^◆\s*/, '') : null;
    if (handle && DECISION.test(type)) {
      // The decider whose edge brings the handle; else one that publishes the decision
      const source = edges.find(
        (edge) => edge.target === id && (edge.data as { messageType?: string } | undefined)?.messageType === type,
      )?.source;
      const decider =
        nodes.find((node) => node.id === source) ?? nodes.find((node) => (dataOf(node).outputTypes ?? []).includes(type));
      const subjects = (dataOf(decider).subscriptions ?? []).filter((subject) => !DECISION.test(subject));
      return {
        type,
        label: handle,
        decision: true,
        note: subjects.length > 0 ? `decision handle · receives the ${subjects.map(shortTypeName).join(' or ')}` : 'decision handle',
        fields: subjects.length === 1 ? fieldsOf(schemas[subjects[0]!]) : [],
        ...(subjects.length > 1 && {
          subjects: subjects.map((subject) => ({
            type: subject,
            label: shortTypeName(subject),
            fields: fieldsOf(schemas[subject]),
          })),
        }),
      };
    }
    const schema = schemas[type];
    return { type, label: shortTypeName(type), decision: false, note: schema ? null : 'no schema known', fields: fieldsOf(schema) };
  });

  // Declared outputs, and what it sent (a source such as `external` declares none)
  const published = [...(data.outputTypes ?? []), ...Object.keys(data.sentByType ?? {})];
  const publishes = [...new Set(published)].map((type): ContractEntry => {
    const question = DECISION.exec(type);
    if (question) {
      return { type, label: shortTypeName(question[1]!), decision: true, note: 'decision · routes to its handles', fields: [] };
    }
    const schema = schemas[type];
    return { type, label: shortTypeName(type), decision: false, note: schema ? null : 'no schema known', fields: fieldsOf(schema) };
  });

  return { consumes, publishes };
}
