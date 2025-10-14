/**
 * Theme Selector Component
 *
 * Searchable dropdown for selecting from 300+ terminal themes.
 * Shows color preview swatches and applies themes in real-time.
 */

import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import { fetchThemeList, fetchTheme, POPULAR_THEMES } from '../../services/themeService';
import { applyTheme, resetToDefaultTheme } from '../../services/themeApplicator';
import { TerminalTheme } from '../../types/theme';

const ThemeSelector: React.FC = () => {
  const [themes, setThemes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [previewTheme, setPreviewTheme] = useState<TerminalTheme | null>(null);

  const currentTheme = useSettingsStore((state) => state.appearance.theme);
  const setTheme = useSettingsStore((state) => state.setTheme);

  // Load theme list on mount
  useEffect(() => {
    loadThemes();
  }, []);

  const loadThemes = async () => {
    try {
      setLoading(true);
      setError(null);
      const themeList = await fetchThemeList();
      setThemes(themeList);
    } catch (err) {
      setError('Failed to load themes. Backend may not be running.');
      console.error('Theme loading error:', err);
      // Fallback to popular themes if API fails
      setThemes(POPULAR_THEMES);
    } finally {
      setLoading(false);
    }
  };

  const handleThemeSelect = async (themeName: string) => {
    try {
      setError(null);
      // Handle default theme (doesn't need API fetch)
      if (themeName === 'default') {
        resetToDefaultTheme();
        setTheme('default');
        setPreviewTheme(null);
        return;
      }
      const theme = await fetchTheme(themeName);
      applyTheme(theme);
      setTheme(themeName);
      setPreviewTheme(null);
    } catch (err) {
      setError(`Failed to load theme "${themeName}"`);
      console.error('Theme application error:', err);
    }
  };

  const handleThemePreview = async (themeName: string) => {
    try {
      // Handle default theme (doesn't need API fetch)
      if (themeName === 'default') {
        resetToDefaultTheme();
        setPreviewTheme(null);
        return;
      }
      const theme = await fetchTheme(themeName);
      setPreviewTheme(theme);
      applyTheme(theme);
    } catch (err) {
      console.error('Theme preview error:', err);
    }
  };

  const handleResetTheme = () => {
    resetToDefaultTheme();
    setTheme('default');
    setPreviewTheme(null);
  };

  // Always include "default" theme at the beginning
  const allThemes = ['default', ...themes];

  const filteredThemes = allThemes.filter((theme) =>
    theme.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const popularThemes = filteredThemes.filter((theme) => POPULAR_THEMES.includes(theme));
  const defaultTheme = filteredThemes.includes('default') ? ['default'] : [];
  const otherThemes = filteredThemes.filter((theme) => !POPULAR_THEMES.includes(theme) && theme !== 'default');

  return (
    <div>
      <div className="settings-field">
        <label htmlFor="theme-search" className="settings-label">
          Search Themes
        </label>
        <input
          id="theme-search"
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search 300+ themes..."
          className="settings-input"
          disabled={loading}
        />
      </div>

      {error && (
        <div style={{
          padding: 'var(--space-component-sm)',
          background: 'var(--color-error-bg)',
          color: 'var(--color-error-light)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 'var(--space-component-md)',
          fontSize: 'var(--font-size-caption)',
        }}>
          {error}
        </div>
      )}

      {loading && (
        <div style={{
          padding: 'var(--space-component-md)',
          textAlign: 'center',
          color: 'var(--color-text-secondary)',
        }}>
          Loading themes...
        </div>
      )}

      {!loading && (
        <>
          {/* Current Theme */}
          <div className="settings-field">
            <label className="settings-label">Current Theme</label>
            <div style={{
              padding: 'var(--space-component-sm)',
              background: 'var(--color-bg-elevated)',
              borderRadius: 'var(--radius-md)',
              border: 'var(--border-default)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <span style={{ color: 'var(--color-text-primary)' }}>
                {currentTheme === 'default' ? 'Default (Flock)' : currentTheme}
              </span>
              {currentTheme !== 'default' && (
                <button
                  onClick={handleResetTheme}
                  style={{
                    padding: '4px 8px',
                    background: 'transparent',
                    border: 'var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--color-text-secondary)',
                    fontSize: 'var(--font-size-caption)',
                    cursor: 'pointer',
                  }}
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Default Theme - Always first */}
          {defaultTheme.length > 0 && (
            <div className="settings-field">
              <label className="settings-label">Built-in Theme</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-xs)' }}>
                <button
                  onClick={() => handleThemeSelect('default')}
                  onMouseEnter={() => handleThemePreview('default')}
                  style={{
                    padding: 'var(--space-component-sm)',
                    background: currentTheme === 'default' ? 'var(--color-primary-500)' : 'var(--color-bg-elevated)',
                    border: 'var(--border-default)',
                    borderRadius: 'var(--radius-md)',
                    color: currentTheme === 'default' ? 'white' : 'var(--color-text-primary)',
                    fontSize: 'var(--font-size-body-sm)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'var(--transition-all)',
                  }}
                >
                  Default (Flock)
                </button>
              </div>
            </div>
          )}

          {/* Popular Themes */}
          {popularThemes.length > 0 && (
            <div className="settings-field">
              <label className="settings-label">Popular Themes</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-xs)' }}>
                {popularThemes.map((theme) => (
                  <button
                    key={theme}
                    onClick={() => handleThemeSelect(theme)}
                    onMouseEnter={() => handleThemePreview(theme)}
                    style={{
                      padding: 'var(--space-component-sm)',
                      background: currentTheme === theme ? 'var(--color-primary-500)' : 'var(--color-bg-elevated)',
                      border: 'var(--border-default)',
                      borderRadius: 'var(--radius-md)',
                      color: currentTheme === theme ? 'white' : 'var(--color-text-primary)',
                      fontSize: 'var(--font-size-body-sm)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'var(--transition-all)',
                    }}
                  >
                    {theme}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* All Other Themes */}
          {otherThemes.length > 0 && (
            <div className="settings-field">
              <label className="settings-label">
                All Themes ({otherThemes.length})
              </label>
              <div style={{
                maxHeight: '300px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--gap-xs)',
                padding: 'var(--space-component-xs)',
                background: 'var(--color-bg-base)',
                borderRadius: 'var(--radius-md)',
              }}>
                {otherThemes.map((theme) => (
                  <button
                    key={theme}
                    onClick={() => handleThemeSelect(theme)}
                    onMouseEnter={() => handleThemePreview(theme)}
                    style={{
                      padding: 'var(--space-component-sm)',
                      background: currentTheme === theme ? 'var(--color-primary-500)' : 'var(--color-bg-elevated)',
                      border: 'var(--border-default)',
                      borderRadius: 'var(--radius-sm)',
                      color: currentTheme === theme ? 'white' : 'var(--color-text-primary)',
                      fontSize: 'var(--font-size-body-sm)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'var(--transition-all)',
                    }}
                  >
                    {theme}
                  </button>
                ))}
              </div>
            </div>
          )}

          {filteredThemes.length === 0 && !loading && (
            <div style={{
              padding: 'var(--space-component-md)',
              textAlign: 'center',
              color: 'var(--color-text-tertiary)',
            }}>
              No themes found matching "{searchQuery}"
            </div>
          )}
        </>
      )}

      {previewTheme && (
        <div style={{
          padding: 'var(--space-component-sm)',
          background: 'var(--color-bg-overlay)',
          borderRadius: 'var(--radius-md)',
          marginTop: 'var(--space-component-md)',
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-tertiary)',
          textAlign: 'center',
        }}>
          Previewing: {previewTheme.name} (click to apply)
        </div>
      )}
    </div>
  );
};

export default ThemeSelector;
