/**
 * What an agent's running run works on. The history records a run's input
 * only once the run has published, so the run's start event names it: the
 * artifact it consumed, or the decision a handle brought, whose subject is
 * what the handle delivers. A consumer of the decision itself gets the
 * decision (an agent has handles or `Decision.of`, never both).
 */

import { useEffect, useState } from 'react';
import { useGraphStore } from '../../../store/graphStore';
import type { ImageSummary } from '../../../utils/imageFields';
import type { Message } from '../unfold/messageHistory';

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

interface ApiArtifact {
  id: string;
  type: string;
  payload: unknown;
  images?: ImageSummary[] | null;
  created_at: string;
  correlation_id?: string | null;
}

/** The artifact, with image data as a description and thumbnails (images can be 20 MB). */
const read = async (id: string): Promise<ApiArtifact> => {
  const response = await fetch(`/api/v1/artifacts/${encodeURIComponent(id)}?images=thumbnails`);
  if (!response.ok) throw new Error(`The artifact could not be read (${response.status})`);
  return response.json();
};

/**
 * The input of the agent's latest started run: `undefined` while it loads,
 * `null` when no running run of it is known (one started before the page
 * connected, or one that consumed nothing).
 */
export function useRunInput(agent: string): Message | null | undefined {
  const id = useGraphStore((state) => {
    let first: string | null = null;
    for (const run of state.inFlight.values()) {
      if (run.agent === agent && run.artifacts.length > 0) first = run.artifacts[0]!;
    }
    return first;
  });
  const handles = useGraphStore((state) => {
    const labels = (state.nodes.find((node) => node.id === agent)?.data as { typeLabels?: Record<string, string> } | undefined)
      ?.typeLabels;
    return Object.values(labels ?? {}).some((label) => label.startsWith('◆'));
  });
  const [read_, setRead] = useState<{ id: string; message: Message | null } | null>(null);

  useEffect(() => {
    if (!id) return;
    let current = true;
    (async () => {
      let artifact = await read(id);
      const subject = handles && DECISION.test(artifact.type)
        ? (artifact.payload as { subject_ids?: string[] } | null)?.subject_ids?.[0]
        : undefined;
      if (subject) artifact = await read(subject);
      return {
        id: artifact.id,
        type: artifact.type,
        direction: 'consumed' as const,
        payload: artifact.payload,
        images: artifact.images ?? undefined,
        at: artifact.created_at,
        correlationId: artifact.correlation_id ?? null,
      };
    })()
      .then((message) => current && setRead({ id, message }))
      .catch(() => current && setRead({ id, message: null }));
    return () => {
      current = false;
    };
  }, [id, handles]);

  if (!id) return null;
  return read_?.id === id ? read_.message : undefined;
}
