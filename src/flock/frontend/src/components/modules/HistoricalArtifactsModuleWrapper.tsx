import React from 'react';
import type { ModuleContext } from './ModuleRegistry';
import HistoricalArtifactsModule from './HistoricalArtifactsModule';

interface HistoricalArtifactsModuleWrapperProps {
  context: ModuleContext;
}

const HistoricalArtifactsModuleWrapper: React.FC<HistoricalArtifactsModuleWrapperProps> = ({ context }) => {
  return <HistoricalArtifactsModule context={context} />;
};

export default HistoricalArtifactsModuleWrapper;
