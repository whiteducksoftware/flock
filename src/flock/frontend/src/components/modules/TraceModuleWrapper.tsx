import React from 'react';
import { ModuleContext } from './ModuleRegistry';
import TraceModule from './TraceModule';

/**
 * Wrapper component for TraceModule that provides the ModuleContext
 */
interface TraceModuleWrapperProps {
  context: ModuleContext;
}

const TraceModuleWrapper: React.FC<TraceModuleWrapperProps> = ({ context }) => {
  return <TraceModule context={context} />;
};

export default TraceModuleWrapper;
