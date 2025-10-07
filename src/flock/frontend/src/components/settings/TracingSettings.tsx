/**
 * Tracing Settings Tab
 *
 * Configure OpenTelemetry tracing options:
 * - Enable/disable auto-tracing
 * - Service whitelist (FLOCK_TRACE_SERVICES)
 * - Operation blacklist (FLOCK_TRACE_IGNORE)
 * - Unified workflow tracing
 * - Clear trace database
 * - View trace statistics
 */

import React, { useState, useEffect } from 'react';
import MultiSelect from './MultiSelect';

interface TraceStats {
  total_spans: number;
  total_traces: number;
  services_count: number;
  oldest_trace: string | null;
  newest_trace: string | null;
  database_size_mb: number;
}

interface TraceServices {
  services: string[];
  operations: string[];
}

const TracingSettings: React.FC = () => {
  // Tracing configuration state
  const [autoTrace, setAutoTrace] = useState(false);
  const [traceFile, setTraceFile] = useState(true);
  const [autoWorkflow, setAutoWorkflow] = useState(false);
  const [traceTtlDays, setTraceTtlDays] = useState<number | null>(30);

  // Service/operation filter state
  const [availableServices, setAvailableServices] = useState<string[]>([]);
  const [availableOperations, setAvailableOperations] = useState<string[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [ignoredOperations, setIgnoredOperations] = useState<string[]>([]);

  // UI state
  const [stats, setStats] = useState<TraceStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    loadTraceServices();
    loadTraceStats();
    loadCurrentSettings();
  }, []);

  const loadTraceServices = async () => {
    try {
      const response = await fetch('/api/traces/services');
      if (!response.ok) throw new Error('Failed to load trace services');
      const data: TraceServices = await response.json();
      setAvailableServices(data.services);
      setAvailableOperations(data.operations);
    } catch (err) {
      console.error('Error loading trace services:', err);
    }
  };

  const loadTraceStats = async () => {
    try {
      const response = await fetch('/api/traces/stats');
      if (!response.ok) throw new Error('Failed to load trace stats');
      const data: TraceStats = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error loading trace stats:', err);
    }
  };

  const loadCurrentSettings = async () => {
    // TODO: Load current .env settings from backend
    // For now, using defaults
    setAutoTrace(true);
    setTraceFile(true);
    setAutoWorkflow(false);
    setTraceTtlDays(30);
    setSelectedServices(['flock', 'agent', 'dspyengine', 'outpututilitycomponent']);
    setIgnoredOperations(['DashboardEventCollector.set_websocket_manager']);
  };

  const handleClearTraces = async () => {
    if (!confirm('Clear all traces from the database? This cannot be undone.')) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch('/api/traces/clear', { method: 'POST' });
      if (!response.ok) throw new Error('Failed to clear traces');

      const result = await response.json();
      if (result.success) {
        setSuccessMessage(`Successfully deleted ${result.deleted_count} trace spans`);
        loadTraceStats(); // Refresh stats
      } else {
        setError(result.error || 'Failed to clear traces');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);
    }
  };

  const handleSaveSettings = async () => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // TODO: Implement backend endpoint to save to .env
      // For now, just show success
      setSuccessMessage('Settings saved successfully (persistence coming soon)');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setLoading(false);
      setTimeout(() => setSuccessMessage(null), 5000);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const formatSize = (sizeMb: number) => {
    if (sizeMb < 1) return `${(sizeMb * 1024).toFixed(1)} KB`;
    return `${sizeMb.toFixed(2)} MB`;
  };

  return (
    <div>
      {/* Error/Success Messages */}
      {error && (
        <div className="settings-message settings-message-error" style={{
          padding: 'var(--space-component-sm)',
          marginBottom: 'var(--space-component-md)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: 'var(--radius-md)',
          color: '#ef4444'
        }}>
          {error}
        </div>
      )}

      {successMessage && (
        <div className="settings-message settings-message-success" style={{
          padding: 'var(--space-component-sm)',
          marginBottom: 'var(--space-component-md)',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: 'var(--radius-md)',
          color: '#10b981'
        }}>
          {successMessage}
        </div>
      )}

      {/* Core Tracing Toggles */}
      <div className="settings-section">
        <h3 className="settings-section-title">OpenTelemetry Tracing</h3>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="auto-trace"
              type="checkbox"
              checked={autoTrace}
              onChange={(e) => setAutoTrace(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="auto-trace" className="settings-checkbox-label">
              Enable auto-tracing (FLOCK_AUTO_TRACE)
            </label>
          </div>
          <p className="settings-description">
            Automatically trace all agent operations and system events with OpenTelemetry
          </p>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="trace-file"
              type="checkbox"
              checked={traceFile}
              onChange={(e) => setTraceFile(e.target.checked)}
              className="settings-checkbox"
              disabled={!autoTrace}
            />
            <label htmlFor="trace-file" className="settings-checkbox-label">
              Store traces in DuckDB (FLOCK_TRACE_FILE)
            </label>
          </div>
          <p className="settings-description">
            Save traces to .flock/traces.duckdb for analysis and debugging
          </p>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="auto-workflow"
              type="checkbox"
              checked={autoWorkflow}
              onChange={(e) => setAutoWorkflow(e.target.checked)}
              className="settings-checkbox"
              disabled={!autoTrace}
            />
            <label htmlFor="auto-workflow" className="settings-checkbox-label">
              Unified workflow tracing (FLOCK_AUTO_WORKFLOW_TRACE)
            </label>
          </div>
          <p className="settings-description">
            Automatically wrap operations in unified workflow traces (experimental)
          </p>
        </div>

        <div className="settings-field">
          <label htmlFor="trace-ttl" className="settings-label">
            Trace Time-To-Live (FLOCK_TRACE_TTL_DAYS)
          </label>
          <p className="settings-description">
            Auto-delete traces older than specified days (leave empty to keep forever)
          </p>
          <input
            id="trace-ttl"
            type="number"
            min="1"
            max="365"
            value={traceTtlDays ?? ''}
            onChange={(e) => setTraceTtlDays(e.target.value ? parseInt(e.target.value) : null)}
            className="settings-input"
            placeholder="30"
            disabled={!autoTrace}
          />
        </div>
      </div>

      {/* Service Whitelist */}
      <div className="settings-section">
        <h3 className="settings-section-title">Service Whitelist (FLOCK_TRACE_SERVICES)</h3>
        <p className="settings-description" style={{ marginBottom: 'var(--space-component-md)' }}>
          Only trace specific services. Leave empty to trace all services.
        </p>

        <MultiSelect
          options={availableServices}
          selected={selectedServices}
          onChange={setSelectedServices}
          placeholder="Select services to trace..."
          disabled={!autoTrace}
        />
      </div>

      {/* Operation Blacklist */}
      <div className="settings-section">
        <h3 className="settings-section-title">Operation Blacklist (FLOCK_TRACE_IGNORE)</h3>
        <p className="settings-description" style={{ marginBottom: 'var(--space-component-md)' }}>
          Exclude specific operations from tracing (format: Service.method)
        </p>

        <MultiSelect
          options={availableOperations}
          selected={ignoredOperations}
          onChange={setIgnoredOperations}
          placeholder="Select operations to ignore..."
          disabled={!autoTrace}
        />
      </div>

      {/* Database Statistics */}
      <div className="settings-section">
        <h3 className="settings-section-title">Trace Database Statistics</h3>

        {stats && (
          <div style={{
            backgroundColor: 'rgba(96, 165, 250, 0.05)',
            border: '1px solid rgba(96, 165, 250, 0.2)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-component-md)'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>
              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Total Spans
                </div>
                <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                  {stats.total_spans.toLocaleString()}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Total Traces
                </div>
                <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                  {stats.total_traces.toLocaleString()}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Services Traced
                </div>
                <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                  {stats.services_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Database Size
                </div>
                <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                  {formatSize(stats.database_size_mb)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Oldest Trace
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)' }}>
                  {formatDate(stats.oldest_trace)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-xs)' }}>
                  Newest Trace
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)' }}>
                  {formatDate(stats.newest_trace)}
                </div>
              </div>
            </div>
          </div>
        )}

        <div style={{ marginTop: 'var(--space-component-md)' }}>
          <button
            onClick={handleClearTraces}
            disabled={loading || !stats || stats.total_spans === 0}
            className="settings-reset-button"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444'
            }}
          >
            {loading ? 'Clearing...' : 'Clear All Traces'}
          </button>
          <p className="settings-description" style={{ marginTop: 'var(--space-xs)' }}>
            Delete all spans and run VACUUM to reclaim disk space
          </p>
        </div>
      </div>

      {/* Save Settings */}
      <div className="settings-section">
        <button
          onClick={handleSaveSettings}
          disabled={loading}
          className="settings-save-button"
          style={{
            backgroundColor: 'rgba(96, 165, 250, 0.1)',
            border: '1px solid rgba(96, 165, 250, 0.3)',
            color: '#60a5fa',
            padding: 'var(--space-component-sm) var(--space-component-md)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--font-size-base)',
            fontWeight: 500,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1
          }}
        >
          {loading ? 'Saving...' : 'Save Tracing Settings'}
        </button>
        <p className="settings-description" style={{ marginTop: 'var(--space-xs)' }}>
          Settings will be persisted to .env file (requires backend restart)
        </p>
      </div>
    </div>
  );
};

export default TracingSettings;
