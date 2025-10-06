/**
 * Theme Type Definitions
 *
 * Terminal theme format matching TOML structure from src/flock/themes/
 */

export interface TerminalColors {
  black: string;
  red: string;
  green: string;
  yellow: string;
  blue: string;
  magenta: string;
  cyan: string;
  white: string;
}

export interface PrimaryColors {
  background: string;
  foreground: string;
}

export interface SelectionColors {
  background: string;
  text: string;
}

export interface CursorColors {
  cursor: string;
  text: string;
}

export interface ThemeColors {
  primary: PrimaryColors;
  normal: TerminalColors;
  bright: TerminalColors;
  selection: SelectionColors;
  cursor: CursorColors;
}

export interface TerminalTheme {
  name: string;
  colors: ThemeColors;
}

export interface ThemeListResponse {
  themes: string[];
}

export interface ThemeDataResponse {
  name: string;
  data: {
    colors: ThemeColors;
  };
}
