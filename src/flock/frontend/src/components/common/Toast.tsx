/**
 * The toast: one short message at the bottom of the board, above the
 * timeline dock, with an optional action. It closes itself after a while.
 */

import React, { useEffect } from 'react';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import styles from './Toast.module.css';

/** How long a toast stays */
export const TOAST_MS = 8000;

const Toast: React.FC = () => {
  const toast = useUIStore((state) => state.toast);
  const dismiss = useUIStore((state) => state.dismissToast);

  // A newer toast starts the clock again
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(dismiss, TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast, dismiss]);

  // The live region stays, so screen readers announce what appears in it
  return (
    <div role="status" aria-live="polite" className={styles.region}>
      {toast && (
        <div className={styles.toast}>
          <Icon name="check" size={15} className={styles.icon} />
          <div className={styles.text}>
            <span className={styles.message} title={toast.title}>
              {toast.message}
            </span>
            {toast.detail && <span className={styles.detail}>{toast.detail}</span>}
          </div>
          {toast.action && (
            <button
              type="button"
              className="btn sm"
              onClick={() => {
                toast.action?.onClick();
                dismiss();
              }}
            >
              {toast.action.label}
            </button>
          )}
          <button type="button" className={`btn ghost sm ${styles.close}`} aria-label="Close" onClick={dismiss}>
            <Icon name="close" size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

export default Toast;
