import { moduleRegistry } from './ModuleRegistry';
import TraceModuleJaegerWrapper from './TraceModuleJaegerWrapper';
import HistoricalArtifactsModuleWrapper from './HistoricalArtifactsModuleWrapper';

/**
 * Register all available modules
 * This should be called during application initialization
 */
export function registerModules(): void {
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
