import React from 'react';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Elegant empty state component with optional CTA
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => {
  return (
    <div className={styles.container}>
      {icon && <div className={styles.icon}>{icon}</div>}

      <h3 className={styles.title}>{title}</h3>

      {description && (
        <p className={styles.description}>{description}</p>
      )}

      {action && (
        <button
          className={styles.action}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

/**
 * Icon components for common empty states
 */
export const EmptyGraphIcon: React.FC = () => (
  <svg width="64" height="64" viewBox="0 0 64 64" fill="none" className={styles.svgIcon}>
    <circle
      cx="20"
      cy="32"
      r="8"
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
    />
    <circle
      cx="44"
      cy="20"
      r="8"
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
    />
    <circle
      cx="44"
      cy="44"
      r="8"
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
    />
    <line
      x1="28"
      y1="32"
      x2="36"
      y2="24"
      stroke="currentColor"
      strokeWidth="2"
      strokeDasharray="4 4"
    />
    <line
      x1="28"
      y1="32"
      x2="36"
      y2="40"
      stroke="currentColor"
      strokeWidth="2"
      strokeDasharray="4 4"
    />
  </svg>
);

export const EmptyMessageIcon: React.FC = () => (
  <svg width="64" height="64" viewBox="0 0 64 64" fill="none" className={styles.svgIcon}>
    <rect
      x="8"
      y="16"
      width="48"
      height="32"
      rx="4"
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
    />
    <line
      x1="16"
      y1="26"
      x2="40"
      y2="26"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      opacity="0.5"
    />
    <line
      x1="16"
      y1="34"
      x2="48"
      y2="34"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      opacity="0.5"
    />
  </svg>
);
