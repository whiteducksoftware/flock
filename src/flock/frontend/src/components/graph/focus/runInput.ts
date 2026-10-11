/**
 * What an agent's running run works on. The history records a run's input
 * only once the run has published, so the run's start event names it: the
 * artifacts it consumed (several for an AND gate or a batch), or the
 * decisions a handle brought, whose subjects are what the handle delivers.
 * A consumer of the decision itself gets the decision (an agent has handles
 * or `Decision.of`, never both).
 */

import { useEffect, useState } from 'react';
import { useGraphStore } from '../../../store/graphStore';
import type { ImageSummary } from '../../../utils/imageFields';
import type { Message } from '../unfold/messageHistory';

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

/** The consumed artifacts read for a run; a batch can hold many more */
const MAX_INPUTS = 5;

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

const messageOf = (artifact: ApiArtifact): Message => ({
  id: artifact.id,
  type: artifact.type,
  direction: 'consumed',
  payload: artifact.payload,
  images: artifact.images ?? undefined,
  at: artifact.created_at,
  correlationId: artifact.correlation_id ?? null,
});

export interface RunInput {
  /** The agent's latest started run, if one is known to be running */
  runId: string | null;
  /** Its inputs: `undefined` while they load, `null` when no run is known (one started before the page connected, or one that consumed nothing) */
  inputs: Message[] | null | undefined;
  /** Consumed artifacts beyond the ones read */
  more: number;
}

export function useRunInput(agent: string): RunInput {
  const runId = useGraphStore((state) => {
    let latest: string | null = null;
    for (const [id, run] of state.inFlight) {
      if (run.agent === agent && run.artifacts.length > 0) latest = id;
    }
    return latest;
  });
  const artifacts = useGraphStore((state) => (runId ? state.inFlight.get(runId)?.artifacts : undefined));
  const handles = useGraphStore((state) => {
    const labels = (state.nodes.find((node) => node.id === agent)?.data as { typeLabels?: Record<string, string> } | undefined)
      ?.typeLabels;
    return Object.values(labels ?? {}).some((label) => label.startsWith('◆'));
  });
  const [read_, setRead] = useState<{ runId: string; inputs: Message[] | null } | null>(null);

  useEffect(() => {
    if (!runId || !artifacts) return;
    let current = true;
    (async () => {
      const consumed = await Promise.all(artifacts.slice(0, MAX_INPUTS).map(read));
      // A handle's decisions stand for their subjects
      const resolved = await Promise.all(
        consumed.map(async (artifact) => {
          const subjects = handles && DECISION.test(artifact.type) ? ((artifact.payload as { subject_ids?: string[] } | null)?.subject_ids ?? []) : [];
          return subjects.length > 0 ? Promise.all(subjects.map(read)) : [artifact];
        }),
      );
      const unique = new Map(resolved.flat().map((artifact) => [artifact.id, messageOf(artifact)]));
      return [...unique.values()];
    })()
      .then((inputs) => current && setRead({ runId, inputs }))
      .catch(() => current && setRead({ runId, inputs: null }));
    return () => {
      current = false;
    };
  }, [runId, artifacts, handles]);

  if (!runId || !artifacts) return { runId: null, inputs: null, more: 0 };
  return {
    runId,
    inputs: read_?.runId === runId ? read_.inputs : undefined,
    more: Math.max(0, artifacts.length - MAX_INPUTS),
  };
}
