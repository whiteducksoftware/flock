import React, { useState } from 'react';
import JsonView from '@uiw/react-json-view';

interface JsonAttributeRendererProps {
  value: string;
  maxStringLength?: number;
}

/**
 * Renders an attribute value, parsing it as JSON if possible and displaying
 * it with a beautiful collapsible JSON viewer. Falls back to plain text if not JSON.
 */
const JsonAttributeRenderer: React.FC<JsonAttributeRendererProps> = ({
  value,
  maxStringLength = 200
}) => {
  const [collapsed, setCollapsed] = useState<boolean | number>(2);

  // Try to parse as JSON
  try {
    const parsed = JSON.parse(value);

    // If it's a simple primitive after parsing, just show it as text
    if (typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean' || parsed === null) {
      return (
        <div style={{
          fontFamily: 'var(--font-family-mono)',
          fontSize: 'var(--font-size-body-xs)',
          color: 'var(--color-text-secondary)',
          wordBreak: 'break-word',
        }}>
          {String(parsed)}
        </div>
      );
    }

    // It's a complex object or array - use JSON viewer
    return (
      <div>
        <div style={{
          display: 'flex',
          gap: 'var(--gap-xs)',
          marginBottom: 'var(--gap-xs)',
        }}>
          <button
            onClick={() => setCollapsed(false)}
            style={{
              padding: '2px 8px',
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-secondary)',
              backgroundColor: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-xs)',
              cursor: 'pointer',
              fontFamily: 'var(--font-family-mono)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-elevated)';
            }}
          >
            Expand All
          </button>
          <button
            onClick={() => setCollapsed(true)}
            style={{
              padding: '2px 8px',
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-secondary)',
              backgroundColor: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-xs)',
              cursor: 'pointer',
              fontFamily: 'var(--font-family-mono)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-elevated)';
            }}
          >
            Collapse All
          </button>
        </div>
        <div style={{
          maxHeight: '400px',
          overflowY: 'auto',
          overflowX: 'auto',
        }}>
          <JsonView
            value={parsed}
            collapsed={collapsed}
            displayDataTypes={false}
            shortenTextAfterLength={0}
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              fontSize: 'var(--font-size-body-xs)',
              fontFamily: 'var(--font-family-mono)',
              padding: 'var(--space-component-sm)',
              borderRadius: 'var(--radius-sm)',
              '--w-rjv-line-color': 'var(--color-text-tertiary)',
              '--w-rjv-key-string': 'var(--color-primary-500)',
              '--w-rjv-info-color': 'var(--color-text-secondary)',
              '--w-rjv-curlybraces-color': 'var(--color-text-tertiary)',
              '--w-rjv-brackets-color': 'var(--color-text-tertiary)',
              '--w-rjv-arrow-color': 'var(--color-text-tertiary)',
              '--w-rjv-edit-color': 'var(--color-primary-500)',
              '--w-rjv-add-color': 'var(--color-success)',
              '--w-rjv-del-color': 'var(--color-error)',
              '--w-rjv-update-color': 'var(--color-warning)',
              '--w-rjv-border-left-color': 'var(--color-border-subtle)',
            } as React.CSSProperties}
          />
        </div>
      </div>
    );
  } catch (e) {
    // Not valid JSON - display as plain text with word wrap
    const displayValue = value.length > maxStringLength
      ? value.substring(0, maxStringLength) + '...'
      : value;

    return (
      <div style={{
        fontFamily: 'var(--font-family-mono)',
        fontSize: 'var(--font-size-body-xs)',
        color: 'var(--color-text-secondary)',
        wordBreak: 'break-word',
        whiteSpace: 'pre-wrap',
      }}>
        {displayValue}
      </div>
    );
  }
};

export default JsonAttributeRenderer;
