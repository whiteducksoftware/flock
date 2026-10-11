import React from 'react';
import TraceModuleJaeger from './TraceModuleJaeger';
import { ModuleContext } from './ModuleRegistry';

interface TraceModuleJaegerWrapperProps {
  context: ModuleContext;
  search?: string;
}

const TraceModuleJaegerWrapper: React.FC<TraceModuleJaegerWrapperProps> = ({ context, search }) => {
  return <TraceModuleJaeger context={context} search={search} />;
};

export default TraceModuleJaegerWrapper;
