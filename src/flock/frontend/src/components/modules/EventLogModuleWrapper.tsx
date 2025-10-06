import React from 'react';
import EventLogModule from './EventLogModule';
import type { ModuleContext } from './ModuleRegistry';

interface EventLogModuleWrapperProps {
  context: ModuleContext;
}

/**
 * Wrapper component for EventLogModule
 * Simply passes through the context provided by ModuleWindow (via useModules hook)
 */
const EventLogModuleWrapper: React.FC<EventLogModuleWrapperProps> = ({ context }) => {
  return <EventLogModule context={context} />;
};

export default EventLogModuleWrapper;
