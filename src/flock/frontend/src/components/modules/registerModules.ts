import { moduleRegistry } from './ModuleRegistry';
import EventLogModuleWrapper from './EventLogModuleWrapper';
import TraceModuleJaegerWrapper from './TraceModuleJaegerWrapper';
import TraceModuleGrafanaWrapper from './TraceModuleGrafanaWrapper';

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

  // Register Jaeger-style Trace Viewer
  moduleRegistry.register({
    id: 'traceViewerJaeger',
    name: 'Trace Viewer (Jaeger)',
    description: 'Timeline and statistics with JSON viewer',
    icon: '🔎',
    component: TraceModuleJaegerWrapper,
  });

  // Register Grafana-style Trace Viewer
  moduleRegistry.register({
    id: 'traceViewerGrafana',
    name: 'Trace Viewer (Grafana)',
    description: 'RED metrics, dependencies, and advanced filters',
    icon: '📊',
    component: TraceModuleGrafanaWrapper,
  });

  // Future modules can be registered here
  // moduleRegistry.register({ ... });
}
