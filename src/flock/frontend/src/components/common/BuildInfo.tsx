import React from 'react';

/**
 * Phase 11: Build Info Display
 *
 * Shows build hash and timestamp in UI corner for deployment verification.
 * Makes it easy to confirm which version of code is running.
 */

const BuildInfo: React.FC = () => {
  const buildHash = typeof __BUILD_HASH__ !== 'undefined' ? __BUILD_HASH__ : 'dev';
  const buildTime = typeof __BUILD_TIMESTAMP__ !== 'undefined' ? __BUILD_TIMESTAMP__ : 'unknown';

  const formattedTime = buildTime !== 'unknown'
    ? new Date(buildTime).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'unknown';

  return (
    <div
      style={{
        fontSize: '10px',
        color: 'var(--color-text-tertiary, #6b7280)',
        fontFamily: 'monospace',
        lineHeight: '1.4',
        opacity: 0.7,
      }}
    >
      <div>Build: {buildHash}</div>
      <div>{formattedTime}</div>
    </div>
  );
};

export default BuildInfo;
