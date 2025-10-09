import React from 'react';
import TraceModuleJaeger from './TraceModuleJaeger';
import { ModuleContext } from './ModuleRegistry';

interface TraceModuleJaegerWrapperProps {
  context: ModuleContext;
}

const TraceModuleJaegerWrapper: React.FC<TraceModuleJaegerWrapperProps> = ({ context }) => {
  return <TraceModuleJaeger context={context} />;
};

export default TraceModuleJaegerWrapper;
