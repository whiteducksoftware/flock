/**
 * Theme Applicator
 *
 * Applies terminal themes to dashboard UI by mapping 8-color palette
 * to CSS custom properties.
 *
 * See: docs/specs/004-ui-improvements/THEME_MAPPING.md
 */

import { TerminalTheme } from '../types/theme';

/**
 * Convert hex color to rgba with alpha channel
 */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Apply a theme to the dashboard by updating CSS variables
 */
export function applyTheme(theme: TerminalTheme): void {
  const root = document.documentElement;
  const { colors } = theme;

  // Background Layers
  root.style.setProperty('--color-bg-base', colors.primary.background);
  root.style.setProperty('--color-bg-elevated', colors.selection.background);
  root.style.setProperty('--color-bg-surface', colors.normal.black);
  root.style.setProperty('--color-bg-overlay', colors.bright.black);
  root.style.setProperty('--color-bg-float', hexToRgba(colors.normal.white, 0.1));

  // Text Colors
  root.style.setProperty('--color-text-primary', colors.primary.foreground);
  root.style.setProperty('--color-text-secondary', colors.bright.white);
  root.style.setProperty('--color-text-tertiary', colors.selection.text);
  root.style.setProperty('--color-text-muted', colors.cursor.text);
  root.style.setProperty('--color-text-on-primary', colors.selection.text);

  // Brand & Accent Colors
  root.style.setProperty('--color-primary-500', colors.normal.blue);
  root.style.setProperty('--color-primary-400', colors.bright.blue);
  root.style.setProperty('--color-primary-600', colors.normal.blue); // Slightly darker for hover
  root.style.setProperty('--color-secondary-500', colors.normal.magenta);
  root.style.setProperty('--color-secondary-400', colors.bright.magenta);
  root.style.setProperty('--color-tertiary-500', colors.normal.cyan);

  // Semantic Status Colors
  root.style.setProperty('--color-success', colors.normal.green);
  root.style.setProperty('--color-success-light', colors.bright.green);
  root.style.setProperty('--color-error', colors.normal.red);
  root.style.setProperty('--color-error-light', colors.bright.red);
  root.style.setProperty('--color-warning', colors.normal.yellow);
  root.style.setProperty('--color-warning-light', colors.bright.yellow);
  root.style.setProperty('--color-info', colors.normal.cyan);
  root.style.setProperty('--color-info-light', colors.bright.cyan);

  // Graph-Specific Colors (can be overridden by user settings)
  // Only set if user hasn't customized them
  const currentIdleColor = root.style.getPropertyValue('--agent-idle-color');
  if (!currentIdleColor || currentIdleColor === '#60a5fa') {
    root.style.setProperty('--agent-idle-color', colors.normal.cyan);
  }

  const currentActiveColor = root.style.getPropertyValue('--agent-active-color');
  if (!currentActiveColor || currentActiveColor === '#10b981') {
    root.style.setProperty('--agent-active-color', colors.normal.green);
  }

  const currentErrorColor = root.style.getPropertyValue('--agent-error-color');
  if (!currentErrorColor || currentErrorColor === '#ef4444') {
    root.style.setProperty('--agent-error-color', colors.normal.red);
  }

  // Border & Divider Colors
  root.style.setProperty('--color-border-default', colors.bright.black);
  root.style.setProperty('--color-border-subtle', hexToRgba(colors.normal.white, 0.2));
  root.style.setProperty('--color-border-strong', colors.cursor.cursor);
  root.style.setProperty('--color-border-focus', colors.normal.blue);
  root.style.setProperty('--color-border-error', colors.normal.red);

  // Special Effect Colors
  root.style.setProperty('--color-glass-bg', hexToRgba(colors.selection.background, 0.8));
  root.style.setProperty('--color-glow-primary', colors.cursor.cursor);
  root.style.setProperty('--shadow-glow-primary', `0 0 0 3px ${hexToRgba(colors.bright.blue, 0.5)}`);
  root.style.setProperty('--shadow-glow-error', `0 0 0 3px ${hexToRgba(colors.bright.red, 0.5)}`);

  // Edge colors
  root.style.setProperty('--color-edge-default', colors.bright.black);
  root.style.setProperty('--color-edge-message', colors.bright.yellow);
  root.style.setProperty('--color-edge-active', colors.bright.blue);

  // Node colors
  root.style.setProperty('--color-node-message-border', colors.normal.magenta);

  console.log(`[Theme] Applied theme: ${theme.name}`);
}

/**
 * Reset to default theme (current design system colors)
 */
export function resetToDefaultTheme(): void {
  const root = document.documentElement;

  // Reset to original design system values
  root.style.setProperty('--color-bg-base', '#0a0a0b');
  root.style.setProperty('--color-bg-elevated', '#121214');
  root.style.setProperty('--color-bg-surface', '#1a1a1e');
  root.style.setProperty('--color-bg-overlay', '#232329');
  root.style.setProperty('--color-bg-float', '#2a2a32');

  root.style.setProperty('--color-text-primary', '#e5e7eb');
  root.style.setProperty('--color-text-secondary', '#9ca3af');
  root.style.setProperty('--color-text-tertiary', '#6b7280');

  root.style.setProperty('--color-primary-500', '#6366f1');
  root.style.setProperty('--color-primary-400', '#818cf8');
  root.style.setProperty('--color-primary-600', '#4f46e5');

  console.log('[Theme] Reset to default theme');
}

/**
 * Get a preview swatch array for a theme (8 colors)
 */
export function getThemePreview(theme: TerminalTheme): string[] {
  return [
    theme.colors.normal.black,
    theme.colors.normal.red,
    theme.colors.normal.green,
    theme.colors.normal.yellow,
    theme.colors.normal.blue,
    theme.colors.normal.magenta,
    theme.colors.normal.cyan,
    theme.colors.normal.white,
  ];
}
