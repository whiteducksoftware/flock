import React from 'react';
import { useWSStore } from '../../store/wsStore';
import styles from './Header.module.css';

interface ConnectionStatusBadgeProps {
  status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  attempts: number;
  error: string | null;
}

const ConnectionStatusBadge: React.FC<ConnectionStatusBadgeProps> = ({ status, attempts, error }) => {
  const statusText = {
    connected: 'Connected',
    connecting: 'Connecting...',
    reconnecting: `Reconnecting (${attempts})...`,
    disconnected: 'Disconnected',
  };

  const badgeClassName = [
    styles.connectionBadge,
    styles[status],
    error ? styles.hasError : '',
  ].filter(Boolean).join(' ');

  const indicatorClassName = [
    styles.statusIndicator,
    styles[status],
  ].join(' ');

  return (
    <div
      className={badgeClassName}
      title={error || undefined}
      role="status"
      aria-live="polite"
      aria-label={`WebSocket connection status: ${statusText[status]}`}
    >
      <div className={indicatorClassName} aria-hidden="true" />
      <span className={styles.statusText}>{statusText[status]}</span>
    </div>
  );
};

export const Header: React.FC = () => {
  const status = useWSStore((state) => state.status);
  const attempts = useWSStore((state) => state.reconnectAttempts);
  const error = useWSStore((state) => state.lastError);

  return <ConnectionStatusBadge status={status} attempts={attempts} error={error} />;
};

export default Header;
