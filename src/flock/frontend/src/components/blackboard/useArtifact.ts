/** An unfolded card's artifact, read by ID with its consumption history, however old it is. */

import { useEffect, useState } from 'react';
import { type ArtifactListItem, fetchArtifact } from '../../services/api';

export function useArtifact(id: string | null): { artifact: ArtifactListItem | null; error: string | null } {
  const [read, setRead] = useState<{ id: string; artifact: ArtifactListItem | null; error: string | null } | null>(null);

  useEffect(() => {
    if (!id) return;
    let current = true;
    fetchArtifact(id, { images: 'thumbnails', embedMeta: true })
      .then((artifact) => current && setRead({ id, artifact, error: null }))
      .catch((reason: unknown) => {
        if (current) setRead({ id, artifact: null, error: reason instanceof Error ? reason.message : String(reason) });
      });
    return () => {
      current = false;
    };
  }, [id]);

  return read?.id === id ? { artifact: read.artifact, error: read.error } : { artifact: null, error: null };
}
