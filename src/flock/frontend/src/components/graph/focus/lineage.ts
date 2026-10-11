/**
 * A node's place in the flow, for the lineage strip of focus mode: who
 * produces what it reads, and who reads what it publishes
 * (docs/internal/design-system/mockups/Focus.dc.html).
 */

import type { Edge, Node } from '@xyflow/react';
import { shortTypeName } from '../../../utils/typeName';

export interface Upstream {
  node: string;
  /** `SupportTicket`, or `Route.billing` for a decision handle */
  label: string;
  decision: boolean;
}

export interface Output {
  type: string;
  /** `TeamReply`, or `Route` for a decision */
  label: string;
  decision: boolean;
  /** Who reads it; `label` is the option a decision consumer takes */
  consumers: { node: string; label: string | null }[];
}

export interface Lineage {
  upstream: Upstream[];
  outputs: Output[];
}

interface FlowData {
  messageType?: string;
  decisionChoice?: string;
}

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

/** The question a decision type answers: `Decision[app.Route]` -> `Route`. */
const questionOf = (type: string): string | null => {
  const match = DECISION.exec(type);
  return match ? shortTypeName(match[1]!) : null;
};

const flowsOf = (edges: Edge[]) =>
  edges.filter((edge) => typeof (edge.data as FlowData | undefined)?.messageType === 'string') as (Edge & {
    data: FlowData & { messageType: string };
  })[];

/**
 * Where `id` sits in the flow. Upstream lists the producers of what it reads;
 * a decision handle reaches one step further, to the producers of the subject
 * the decider decided about, since that is what the handle delivers.
 */
export function lineageOf(id: string, nodes: Node[], edges: Edge[]): Lineage {
  const flows = flowsOf(edges);
  const upstream: Upstream[] = [];
  const add = (entry: Upstream) => {
    if (!upstream.some((known) => known.node === entry.node && known.label === entry.label)) upstream.push(entry);
  };

  for (const edge of flows.filter((flow) => flow.target === id)) {
    const question = questionOf(edge.data.messageType);
    if (question && edge.data.decisionChoice !== undefined) {
      // The subject the decider read comes first
      flows
        .filter((flow) => flow.target === edge.source && !questionOf(flow.data.messageType))
        .forEach((flow) => add({ node: flow.source, label: shortTypeName(flow.data.messageType), decision: false }));
      // Choices come as the option (`billing`, or an id such as `ORP.1.A1`);
      // yes/no, scale and checklist labels come qualified (`Escalate.yes`)
      const choice = edge.data.decisionChoice;
      add({ node: edge.source, label: choice.startsWith(`${question}.`) ? choice : `${question}.${choice}`, decision: true });
    } else {
      add({ node: edge.source, label: shortTypeName(edge.data.messageType), decision: false });
    }
  }

  const declared = ((nodes.find((node) => node.id === id)?.data as { outputTypes?: string[] } | undefined)?.outputTypes ?? []);
  const published = flows.filter((flow) => flow.source === id);
  const types = [...new Set([...declared, ...published.map((flow) => flow.data.messageType)])];
  const outputs = types.map((type) => {
    const question = questionOf(type);
    const consumers: Output['consumers'] = [];
    published
      .filter((flow) => flow.data.messageType === type)
      .forEach((flow) => {
        const label = flow.data.decisionChoice ?? null;
        if (!consumers.some((known) => known.node === flow.target && known.label === label)) {
          consumers.push({ node: flow.target, label });
        }
      });
    return { type, label: question ?? shortTypeName(type), decision: question !== null, consumers };
  });

  return { upstream, outputs };
}
