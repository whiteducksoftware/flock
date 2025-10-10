import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchGraphSnapshot } from './api/graph';
import type { ServerGraphSnapshot, ViewMode } from './api/types';

const VIEW_MODES: ViewMode[] = ['agent', 'blackboard'];

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const INITIAL_STATE: ServerGraphSnapshot = {
  generatedAt: new Date().toISOString(),
  viewMode: 'agent',
  nodes: [],
  edges: [],
  totalArtifacts: 0,
  truncated: false,
};

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('agent');
  const [snapshot, setSnapshot] = useState<ServerGraphSnapshot>(INITIAL_STATE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSnapshot = useCallback(
    async (nextMode: ViewMode) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchGraphSnapshot(nextMode);
        setSnapshot(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadSnapshot(viewMode);
  }, [viewMode, loadSnapshot]);

  const stats = useMemo(
    () => [
      { label: 'Nodes', value: snapshot.nodes.length },
      { label: 'Edges', value: snapshot.edges.length },
      { label: 'Artifacts', value: snapshot.totalArtifacts },
      { label: 'Truncated', value: snapshot.truncated ? 'Yes' : 'No' },
    ],
    [snapshot]
  );

  return (
    <main>
      <header>
        <h1>Flock Dashboard v2</h1>
        <p style={{ margin: 0, color: 'var(--color-text-tertiary)' }}>
          Server-driven graph snapshot explorer
        </p>
      </header>

      <section style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {VIEW_MODES.map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                background: viewMode === mode ? '#1f6feb' : '#30363d',
              }}
            >
              {mode === 'agent' ? 'Agent view' : 'Blackboard view'}
            </button>
          ))}
        </div>
        <button onClick={() => loadSnapshot(viewMode)} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh snapshot'}
        </button>
      </section>

      {error && (
        <section style={{ borderColor: '#f85149', color: '#f85149' }}>
          <strong>Error:</strong> {error}
        </section>
      )}

      <section>
        <div className="stats-grid">
          {stats.map((stat) => (
            <SummaryCard key={stat.label} label={stat.label} value={stat.value} />
          ))}
        </div>
      </section>

      <section>
        <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Latest snapshot</h2>
        <p style={{ margin: '0.25rem 0', color: 'var(--color-text-tertiary)' }}>
          Generated at: {new Date(snapshot.generatedAt).toLocaleString()} ({snapshot.viewMode} mode)
        </p>
        <pre
          style={{
            background: 'rgba(13, 17, 23, 0.6)',
            borderRadius: '12px',
            padding: '1rem',
            maxHeight: '360px',
            overflow: 'auto',
            margin: 0,
            fontSize: '0.85rem',
          }}
        >
          {JSON.stringify(snapshot.nodes.slice(0, 3), null, 2)}
          {snapshot.nodes.length > 3 ? '\n…' : ''}
        </pre>
      </section>
    </main>
  );
}

export default App;
