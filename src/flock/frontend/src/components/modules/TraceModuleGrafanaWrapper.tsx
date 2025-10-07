import React from 'react';
import TraceModuleGrafana from './TraceModuleGrafana';
import { ModuleContext } from './ModuleRegistry';

interface TraceModuleGrafanaWrapperProps {
  context: ModuleContext;
}

const TraceModuleGrafanaWrapper: React.FC<TraceModuleGrafanaWrapperProps> = ({ context }) => {
  return <TraceModuleGrafana context={context} />;
};

export default TraceModuleGrafanaWrapper;
