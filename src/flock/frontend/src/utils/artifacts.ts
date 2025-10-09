import type { ArtifactListItem } from '../services/api';
import type { Message } from '../types/graph';

export function mapArtifactToMessage(item: ArtifactListItem): Message {
  const consumedBy =
    item.consumed_by ??
    (item.consumptions ? Array.from(new Set(item.consumptions.map((record) => record.consumer))) : []);

  return {
    id: item.id,
    type: item.type,
    payload: item.payload,
    timestamp: new Date(item.created_at).getTime(),
    correlationId: item.correlation_id ?? '',
    producedBy: item.produced_by,
    tags: item.tags || [],
    visibilityKind: item.visibility_kind || item.visibility?.kind || 'Unknown',
    partitionKey: item.partition_key ?? null,
    version: item.version ?? 1,
    isStreaming: false,
    streamingText: '',
    consumedBy,
  };
}
