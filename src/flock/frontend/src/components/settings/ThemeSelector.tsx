/**
 * The theme picker (Settings › Appearance): Graphite and Paper, the popular
 * terminal themes, and every other one, with a search. Hovering a terminal
 * theme previews it; leaving puts the chosen theme back, and a click keeps it.
 */

import React, { useEffect, useRef, useState } from 'react';
import { fetchTheme, fetchThemeList, POPULAR_THEMES } from '../../services/themeService';
import {
  type AppliedTheme,
  applyThemeByName,
  appliedTheme,
  BUILT_IN_THEMES,
  builtInTheme,
  restoreTheme,
} from '../../services/themeApplicator';
import { useSettingsStore } from '../../store/settingsStore';
import styles from './ThemeSelector.module.css';

const THEME_LABELS: Record<'graphite' | 'paper', string> = { graphite: 'Graphite', paper: 'Paper' };

const ThemeSelector: React.FC = () => {
  const [themes, setThemes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  // The terminal theme shown while the pointer is on it, and what the page showed before
  const [preview, setPreview] = useState<string | null>(null);
  const before = useRef<AppliedTheme | null>(null);

  const currentTheme = useSettingsStore((state) => state.appearance.theme);
  const setTheme = useSettingsStore((state) => state.setTheme);

  useEffect(() => {
    let live = true;
    setLoading(true);
    fetchThemeList()
      .then((list) => live && setThemes(list))
      .catch((err) => {
        if (!live) return;
        console.error('Theme loading error:', err);
        // The popular ones still work offline from the list
        setError('Failed to load themes. Backend may not be running.');
        setThemes(POPULAR_THEMES);
      })
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, []);

  const select = async (themeName: string) => {
    try {
      setError(null);
      setPreview(null);
      before.current = null;
      // Only the latest choice applies and is stored (null: a newer one won)
      const applied = await applyThemeByName(themeName, document.documentElement, fetchTheme, false);
      if (applied !== null) setTheme(applied);
    } catch (err) {
      setError(`Failed to load theme "${themeName}"`);
      console.error('Theme application error:', err);
    }
  };

  // Graphite and Paper apply on click only: a preview of them would be the theme itself
  const startPreview = async (themeName: string) => {
    if (builtInTheme(themeName)) return;
    before.current ??= appliedTheme();
    setPreview(themeName);
    try {
      await applyThemeByName(themeName, document.documentElement, fetchTheme, false);
    } catch (err) {
      console.error('Theme preview error:', err);
    }
  };

  // Back to what the page showed, as it was: no request that could fail; a preview
  // still loading gives way to it
  const endPreview = () => {
    const shown = before.current;
    before.current = null;
    setPreview(null);
    if (shown) restoreTheme(shown);
  };

  const query = searchQuery.trim().toLowerCase();
  const builtIns = BUILT_IN_THEMES.filter((theme) => theme.includes(query) || THEME_LABELS[theme].toLowerCase().includes(query));
  const found = themes.filter((theme) => theme.toLowerCase().includes(query));
  const popular = found.filter((theme) => POPULAR_THEMES.includes(theme));
  const others = found.filter((theme) => !POPULAR_THEMES.includes(theme));
  const current = builtInTheme(currentTheme) ?? currentTheme;

  const option = (theme: string, label = theme) => (
    <button
      key={theme}
      type="button"
      className={styles.theme}
      aria-pressed={current === theme}
      onClick={() => void select(theme)}
      onMouseEnter={() => void startPreview(theme)}
      onMouseLeave={endPreview}
    >
      {label}
    </button>
  );

  return (
    <div className={styles.picker}>
      <div className="settings-field">
        <label htmlFor="theme-search" className="settings-label">
          Search Themes
        </label>
        <input
          id="theme-search"
          type="text"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search 300+ themes…"
          className="settings-input"
          disabled={loading}
        />
      </div>

      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {loading && <p className={styles.note}>Loading themes…</p>}

      {!loading && (
        <>
          {builtIns.length > 0 && (
            <section className={styles.group} aria-labelledby="themes-built-in">
              <h4 id="themes-built-in" className={styles.groupLabel}>
                Built-in Themes
              </h4>
              <div className={styles.builtIns}>{builtIns.map((theme) => option(theme, THEME_LABELS[theme]))}</div>
            </section>
          )}

          {popular.length > 0 && (
            <section className={styles.group} aria-labelledby="themes-popular">
              <h4 id="themes-popular" className={styles.groupLabel}>
                Popular Themes
              </h4>
              <div className={styles.list}>{popular.map((theme) => option(theme))}</div>
            </section>
          )}

          {others.length > 0 && (
            <section className={styles.group} aria-labelledby="themes-all">
              <h4 id="themes-all" className={styles.groupLabel}>
                All Themes <span className="num">{others.length}</span>
              </h4>
              <div className={`${styles.list} ${styles.scroll}`}>{others.map((theme) => option(theme))}</div>
            </section>
          )}

          {builtIns.length + found.length === 0 && <p className={styles.note}>No themes found matching "{searchQuery}"</p>}
        </>
      )}

      {preview && (
        <p role="status" className={styles.note}>
          Previewing {preview}; click to keep it
        </p>
      )}
    </div>
  );
};

export default ThemeSelector;
