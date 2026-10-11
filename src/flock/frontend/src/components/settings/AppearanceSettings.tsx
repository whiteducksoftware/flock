/**
 * Appearance Settings Tab: the theme (Graphite, Paper and the terminal
 * themes). Status colors are the design's signals, and the chip level
 * replaced the compact view (docs/internal/design-system/README.md).
 */

import React from 'react';
import ThemeSelector from './ThemeSelector';

const AppearanceSettings: React.FC = () => (
  <div>
    <div className="settings-section">
      <h3 className="settings-section-title">Theme</h3>

      <p className="settings-description" style={{ marginBottom: 'var(--space-component-md)' }}>
        Choose from 300+ terminal color themes. Themes are loaded from the backend and applied in real-time.
      </p>

      <ThemeSelector />
    </div>
  </div>
);

export default AppearanceSettings;
