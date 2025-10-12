import { memo } from 'react';
import { NodeProps, Handle, Position } from '@xyflow/react';
import JsonView from '@uiw/react-json-view';

// UI Optimization Migration (Phase 4.1 - Spec 002): Backend GraphNode.data is Record<string, any>
// Message/artifact-specific properties populated by backend snapshot
const MessageNode = memo(({ id, data, selected }: NodeProps) => {
  const nodeData = data as Record<string, any>;
  const artifactType = nodeData.artifactType;
  const payload = nodeData.payload;
  const producedBy = nodeData.producedBy;
  const timestamp = nodeData.timestamp;
  const isStreaming = nodeData.isStreaming || false;
  const streamingText = nodeData.streamingText || '';

  // Phase 6: Show artifact ID for debugging/verification
  const artifactId = id; // Node ID is the artifact ID

  return (
    <div
      className={`message-node ${selected ? 'selected' : ''}`}
      style={{
        padding: '12px',
        border: `2px solid ${selected ? '#8b5cf6' : '#e2e8f0'}`,
        borderRadius: '8px',
        backgroundColor: '#fefce8',
        minWidth: '300px',
        maxWidth: '600px',
        width: 'auto',
        boxShadow: selected ? '0 4px 12px rgba(139,92,246,0.3)' : '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.2s ease',
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      {/* Header */}
      <div style={{
        marginBottom: '10px',
        paddingBottom: '8px',
        borderBottom: '1px solid #e2e8f0'
      }}>
        <div style={{
          fontWeight: 700,
          fontSize: '14px',
          marginBottom: '4px',
          color: '#713f12',
          fontFamily: 'monospace'
        }}>
          {artifactType}
        </div>
        <div style={{
          fontSize: '10px',
          color: '#a8a29e',
          marginBottom: '4px',
          fontFamily: 'monospace',
          wordBreak: 'break-all'
        }}>
          id: {artifactId}
        </div>
        <div style={{
          fontSize: '11px',
          color: '#a8a29e',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>by: <span style={{ color: '#78716c', fontWeight: 600 }}>{producedBy}</span></div>
          <div>{new Date(timestamp).toLocaleTimeString()}</div>
        </div>
      </div>

      {/* Content: Streaming text or JSON Payload */}
      <div style={{
        fontSize: '12px',
        maxHeight: '600px',
        overflowY: 'auto',
        overflowX: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word'
      }}>
        {isStreaming ? (
          /* Streaming: Show raw text with cursor */
          <div style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            color: '#78716c',
            lineHeight: '1.5'
          }}>
            {streamingText}
            <span style={{
              display: 'inline-block',
              width: '8px',
              height: '14px',
              backgroundColor: '#8b5cf6',
              marginLeft: '2px',
              animation: 'blink 1s step-end infinite'
            }} />
            <style>{`
              @keyframes blink {
                0%, 50% { opacity: 1; }
                51%, 100% { opacity: 0; }
              }
            `}</style>
          </div>
        ) : (
          /* Complete: Show beautiful JSON */
          <JsonView
            value={payload}
            collapsed={false}
            displayDataTypes={false}
            shortenTextAfterLength={0}
            style={{
              backgroundColor: 'transparent',
              fontSize: '12px',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              '--w-rjv-line-color': '#78716c',
              '--w-rjv-key-string': '#713f12',
              '--w-rjv-info-color': '#a8a29e',
            } as React.CSSProperties}
          />
        )}
      </div>
    </div>
  );
});

MessageNode.displayName = 'MessageNode';

export default MessageNode;
