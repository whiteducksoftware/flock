/**
 * What an unfolded artifact card shows from the board's snapshot: a
 * decision's probabilities and review, an explanation, a coverage, image
 * thumbnails. The decision displays keep their look until the decision kit
 * (#566).
 */

import React from 'react';
import ImageThumbnails from '../common/ImageThumbnails';
import {
  CoverageCard,
  type CoverageInfo,
  DecisionBars,
  type DecisionInfo,
  ExplanationCard,
  type ExplanationInfo,
} from '../graph/DecisionDisplay';
import type { ImageSummary } from '../../utils/imageFields';

export interface ArtifactViews {
  decision?: DecisionInfo;
  explanation?: ExplanationInfo;
  coverage?: CoverageInfo;
  images?: ImageSummary[];
}

/** `data` is the artifact node's data; the views it may carry are read from it */
const ArtifactBody: React.FC<{ id: string; data: Record<string, unknown> }> = ({ id, data: node }) => {
  const data = node as ArtifactViews;
  return (
    <>
      {data.decision && <DecisionBars decision={data.decision} artifactId={id} />}
      {data.explanation && <ExplanationCard explanation={data.explanation} />}
      {data.coverage && <CoverageCard coverage={data.coverage} />}
      {data.images && data.images.length > 0 && <ImageThumbnails artifactId={id} images={data.images} />}
    </>
  );
};

export default ArtifactBody;
