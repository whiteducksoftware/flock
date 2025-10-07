import { moduleRegistry } from './ModuleRegistry';
import EventLogModuleWrapper from './EventLogModuleWrapper';
import TraceModuleWrapper from './TraceModuleWrapper';

/**
 * Register all available modules
 * This should be called during application initialization
 */
export function registerModules(): void {
  // Register EventLog module
  moduleRegistry.register({
    id: 'eventLog',
    name: 'Event Log',
    description: 'View and filter system events',
    icon: '📋',
    component: EventLogModuleWrapper,
  });

  // Register Trace Viewer module
  moduleRegistry.register({
    id: 'traceViewer',
    name: 'Trace Viewer',
    description: 'OpenTelemetry traces with waterfall visualization',
    icon: '🔍',
    component: TraceModuleWrapper,
  });

  // Future modules can be registered here
  // moduleRegistry.register({ ... });
}
