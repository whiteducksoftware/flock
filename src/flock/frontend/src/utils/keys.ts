/** Shortcut labels for the platform: ⌘ on a Mac, Ctrl elsewhere. */

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent);

/** `⌘K` on a Mac, `Ctrl+K` elsewhere */
export const modKey = (key: string): string => (isMac ? `⌘${key}` : `Ctrl+${key}`);
