import { moduleRegistry } from './ModuleRegistry';
import EventLogModuleWrapper from './EventLogModuleWrapper';
import TraceModuleJaegerWrapper from './TraceModuleJaegerWrapper';
import HistoricalArtifactsModuleWrapper from './HistoricalArtifactsModuleWrapper';

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

  // Register Trace Viewer with Timeline, Statistics, RED Metrics, and Dependencies
  moduleRegistry.register({
    id: 'traceViewerJaeger',
    name: 'Trace Viewer',
    description: 'Timeline, Statistics, RED Metrics, and Dependencies',
    icon: '🔎',
    component: TraceModuleJaegerWrapper,
  });

  moduleRegistry.register({
    id: 'historicalArtifacts',
    name: 'Historical Blackboard',
    description: 'Browse persisted artifacts and retention metrics',
    icon: '📚',
    component: HistoricalArtifactsModuleWrapper,
  });

  // Future modules can be registered here
  // moduleRegistry.register({ ... });
}
