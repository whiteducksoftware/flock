import { moduleRegistry } from './ModuleRegistry';
import EventLogModuleWrapper from './EventLogModuleWrapper';

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

  // Future modules can be registered here
  // moduleRegistry.register({ ... });
}
