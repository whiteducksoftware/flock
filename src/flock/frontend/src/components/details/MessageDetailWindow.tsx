import React, { useCallback, useEffect, useState } from 'react';
import { Rnd } from 'react-rnd';
import { useUIStore } from '../../store/uiStore';
import JsonAttributeRenderer from '../modules/JsonAttributeRenderer';
import { fetchArtifacts, type ArtifactListItem } from '../../services/api';

interface MessageDetailWindowProps {
  nodeId: string;
}

const MessageDetailWindow: React.FC<MessageDetailWindowProps> = ({ nodeId }) => {
  const window = useUIStore((state) => state.detailWindows.get(nodeId));
  const updateDetailWindow = useUIStore((state) => state.updateDetailWindow);
  const closeDetailWindow = useUIStore((state) => state.closeDetailWindow);

  const [artifact, setArtifact] = useState<ArtifactListItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleClose = useCallback(() => {
    closeDetailWindow(nodeId);
  }, [nodeId, closeDetailWindow]);

  // Fetch artifact details from backend
  // Note: We query recent artifacts and filter client-side by ID
  // because there's no single artifact endpoint yet
  useEffect(() => {
    const fetchArtifactDetails = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Fetch recent artifacts with consumption metadata
        const response = await fetchArtifacts({
          limit: 100,
          embedMeta: true,
        });

        // Find the artifact matching this node ID
        const matchingArtifact = response.items.find((item) => item.id === nodeId);

        if (!matchingArtifact) {
          throw new Error('Artifact not found');
        }

        setArtifact(matchingArtifact);
      } catch (err) {
        console.error('Failed to fetch artifact details:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchArtifactDetails();
  }, [nodeId]);

  if (!window) return null;

  const { position, size } = window;

  return (
    <Rnd
      position={position}
      size={size}
      onDragStop={(_e, d) => {
        updateDetailWindow(nodeId, {
          position: { x: d.x, y: d.y },
        });
      }}
      onResizeStop={(_e, _direction, ref, _delta, position) => {
        updateDetailWindow(nodeId, {
          size: {
            width: parseInt(ref.style.width, 10),
            height: parseInt(ref.style.height, 10),
          },
          position,
        });
      }}
      minWidth={600}
      minHeight={400}
      bounds="parent"
      dragHandleClassName="window-header"
      style={{
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        pointerEvents: 'all',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: '100%',
          background: 'var(--color-glass-bg)',
          border: 'var(--border-width-1) solid var(--color-glass-border)',
          borderRadius: 'var(--radius-xl)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-xl)',
          backdropFilter: 'blur(var(--blur-lg))',
          WebkitBackdropFilter: 'blur(var(--blur-lg))',
        }}
      >
        {/* Header */}
        <div
          className="window-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-component-md) var(--space-component-lg)',
            background: 'rgba(42, 42, 50, 0.5)',
            borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
            cursor: 'move',
            userSelect: 'none',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-xs)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-md)' }}>
              <div
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: 'var(--radius-circle)',
                  background: 'var(--color-warning)',
                  boxShadow: '0 0 8px var(--color-warning)',
                }}
              />
              <span
                style={{
                  color: 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-body-sm)',
                  fontWeight: 'var(--font-weight-semibold)',
                  fontFamily: 'var(--font-family-sans)',
                }}
              >
                Message: {artifact?.type || nodeId}
              </span>
            </div>
            <div
              style={{
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-tertiary)',
                fontFamily: 'var(--font-family-mono)',
                paddingLeft: 'calc(10px + var(--gap-md))', // Align with message text
              }}
            >
              id: {nodeId}
            </div>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close window"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-h3)',
              cursor: 'pointer',
              padding: 'var(--spacing-1) var(--spacing-2)',
              lineHeight: 1,
              borderRadius: 'var(--radius-md)',
              transition: 'var(--transition-colors)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-error)';
              e.currentTarget.style.background = 'var(--color-error-bg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-secondary)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            background: 'var(--color-bg-elevated)',
            color: 'var(--color-text-primary)',
            padding: 'var(--space-layout-md)',
          }}
        >
          {isLoading ? (
            <div
              style={{
                textAlign: 'center',
                padding: 'var(--space-layout-lg)',
                color: 'var(--color-text-muted)',
                fontSize: 'var(--font-size-body-sm)',
                fontFamily: 'var(--font-family-sans)',
              }}
            >
              Loading artifact details...
            </div>
          ) : error ? (
            <div
              style={{
                textAlign: 'center',
                padding: 'var(--space-layout-lg)',
                color: 'var(--color-error-light)',
                fontSize: 'var(--font-size-body-sm)',
                fontFamily: 'var(--font-family-sans)',
              }}
            >
              Error: {error}
            </div>
          ) : artifact ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-lg)' }}>
              {/* Timestamp */}
              <div>
                <div
                  style={{
                    fontSize: 'var(--font-size-caption)',
                    color: 'var(--color-text-tertiary)',
                    fontFamily: 'var(--font-family-sans)',
                  }}
                >
                  {new Date(artifact.created_at).toLocaleString()}
                </div>
              </div>

              {/* Two-column layout: Metadata (left) + Payload (right) */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(250px, 350px) 1fr',
                  gap: 'var(--gap-xl)',
                }}
              >
                {/* Metadata Section - Left Column */}
                <div>
                <h3
                  style={{
                    fontSize: 'var(--font-size-body)',
                    fontWeight: 'var(--font-weight-semibold)',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-family-sans)',
                    marginBottom: 'var(--space-component-md)',
                  }}
                >
                  METADATA
                </h3>
                <dl
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr',
                    gap: 'var(--gap-sm) var(--gap-lg)',
                    fontSize: 'var(--font-size-body-sm)',
                    fontFamily: 'var(--font-family-sans)',
                  }}
                >
                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Produced By
                  </dt>
                  <dd style={{ color: 'var(--color-text-primary)', margin: 0 }}>{artifact.produced_by}</dd>

                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Correlation
                  </dt>
                  <dd
                    style={{
                      color: 'var(--color-text-primary)',
                      margin: 0,
                      fontFamily: 'var(--font-family-mono)',
                      fontSize: 'var(--font-size-caption)',
                    }}
                  >
                    {artifact.correlation_id || '—'}
                  </dd>

                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Partition
                  </dt>
                  <dd style={{ color: 'var(--color-text-primary)', margin: 0 }}>
                    {artifact.partition_key || '—'}
                  </dd>

                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Tags
                  </dt>
                  <dd style={{ color: 'var(--color-text-primary)', margin: 0 }}>
                    {artifact.tags.length > 0 ? artifact.tags.join(', ') : '—'}
                  </dd>

                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Visibility
                  </dt>
                  <dd style={{ color: 'var(--color-text-primary)', margin: 0 }}>
                    {artifact.visibility_kind || artifact.visibility?.kind || 'Unknown'}
                  </dd>

                  <dt style={{ color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-semibold)' }}>
                    Consumed By
                  </dt>
                  <dd style={{ color: 'var(--color-text-primary)', margin: 0 }}>
                    {artifact.consumed_by && artifact.consumed_by.length > 0
                      ? artifact.consumed_by.join(', ')
                      : '—'}
                  </dd>
                </dl>
              </div>

                {/* Payload Section - Right Column */}
                <div>
                  <h3
                    style={{
                      fontSize: 'var(--font-size-body)',
                      fontWeight: 'var(--font-weight-semibold)',
                      color: 'var(--color-text-primary)',
                      fontFamily: 'var(--font-family-sans)',
                      marginBottom: 'var(--space-component-md)',
                    }}
                  >
                    PAYLOAD
                  </h3>
                  <div
                    style={{
                      background: 'var(--color-bg-base)',
                      border: 'var(--border-default)',
                      borderRadius: 'var(--radius-md)',
                      padding: 'var(--space-component-md)',
                      fontFamily: 'var(--font-family-mono)',
                      fontSize: 'var(--font-size-caption)',
                      maxHeight: '400px',
                      overflow: 'auto',
                    }}
                  >
                    <JsonAttributeRenderer
                      value={JSON.stringify(artifact.payload, null, 2)}
                      maxStringLength={Number.POSITIVE_INFINITY}
                    />
                  </div>
                </div>
              </div>

              {/* Consumption History Section - Full Width Below */}
              <div>
                <h3
                  style={{
                    fontSize: 'var(--font-size-body)',
                    fontWeight: 'var(--font-weight-semibold)',
                    color: 'var(--color-text-primary)',
                    fontFamily: 'var(--font-family-sans)',
                    marginBottom: 'var(--space-component-md)',
                  }}
                >
                  CONSUMPTION HISTORY
                </h3>
                {artifact.consumptions && artifact.consumptions.length > 0 ? (
                  <ul
                    style={{
                      listStyle: 'none',
                      padding: 0,
                      margin: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 'var(--gap-md)',
                    }}
                  >
                    {artifact.consumptions.map((entry) => (
                      <li
                        key={`${entry.consumer}-${entry.consumed_at}`}
                        style={{
                          padding: 'var(--space-component-md)',
                          background: 'var(--color-bg-surface)',
                          border: 'var(--border-default)',
                          borderRadius: 'var(--radius-md)',
                          fontFamily: 'var(--font-family-sans)',
                          fontSize: 'var(--font-size-body-sm)',
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 'var(--font-weight-semibold)',
                            color: 'var(--color-text-primary)',
                            marginBottom: 'var(--spacing-1)',
                          }}
                        >
                          {entry.consumer}
                        </div>
                        <div
                          style={{
                            fontSize: 'var(--font-size-caption)',
                            color: 'var(--color-text-tertiary)',
                          }}
                        >
                          {new Date(entry.consumed_at).toLocaleString()}
                        </div>
                        {entry.run_id && (
                          <div
                            style={{
                              display: 'inline-block',
                              marginTop: 'var(--spacing-2)',
                              padding: 'var(--spacing-1) var(--spacing-2)',
                              background: 'var(--color-primary-900)',
                              color: 'var(--color-primary-300)',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: 'var(--font-size-overline)',
                              fontFamily: 'var(--font-family-mono)',
                            }}
                          >
                            Run {entry.run_id}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p
                    style={{
                      color: 'var(--color-text-muted)',
                      fontSize: 'var(--font-size-body-sm)',
                      fontFamily: 'var(--font-family-sans)',
                      fontStyle: 'italic',
                    }}
                  >
                    No consumers recorded for this artifact.
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </Rnd>
  );
};

export default MessageDetailWindow;
