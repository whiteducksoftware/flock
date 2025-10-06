/**
 * Theme Service
 *
 * Fetches terminal themes from the backend API.
 * Themes are loaded from TOML files in src/flock/themes/
 */

import { TerminalTheme, ThemeListResponse, ThemeDataResponse } from '../types/theme';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

/**
 * Fetch list of available theme names
 */
export async function fetchThemeList(): Promise<string[]> {
  try {
    const response = await fetch(`${BASE_URL}/themes`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch themes: ${response.statusText}`);
    }

    const data: ThemeListResponse = await response.json();
    return data.themes;
  } catch (error) {
    console.error('Error fetching theme list:', error);
    throw error;
  }
}

/**
 * Fetch a specific theme by name
 */
export async function fetchTheme(themeName: string): Promise<TerminalTheme> {
  try {
    const response = await fetch(`${BASE_URL}/themes/${themeName}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch theme "${themeName}": ${response.statusText}`);
    }

    const data: ThemeDataResponse = await response.json();
    return {
      name: data.name,
      colors: data.data.colors,
    };
  } catch (error) {
    console.error(`Error fetching theme "${themeName}":`, error);
    throw error;
  }
}

/**
 * Get popular/recommended themes
 */
export const POPULAR_THEMES = [
  'dracula',
  'nord',
  'catppuccin-mocha',
  'tokyonight',
  'gruvboxdark',
  'solarized-dark',
  'github-dark',
  'one-half-dark',
  'monokai',
  'material',
];
